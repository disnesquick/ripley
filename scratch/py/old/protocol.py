from unstuck import *
from serialize import *
from shared import *
from errors import *
import headers

class Protocol:
	def __init__(self, connection, bus):
		self.bus = bus
		self.cachedTransverse = {}
	
	##
	# Operations for preparing a packet
	##
	
	def beginWrite(self, destination, header):
		""" Returns a valid output buffer to write to. As a root gateway then
		    the buffer will be the final raw buffer provided by the route.
		"""
		buf = destination.getOutputBuffer()
		buf.write(header)
		return buf
	
	##
	# Incoming message routing
	##
	def handleReceived(self, origin, inStream):
		""" Processes the current waiting packet from inStream and acts according
		    to the header byte received as the first byte read.
		"""
		header = inStream.read(1)
		if header == headers.HEADER_RESOLVE:
			self.receiveResolve(origin, inStream)
		elif header == headers.HEADER_NOTIFY:
			self.receiveNotify(origin, inStream)
		elif header == headers.HEADER_EVAL:
			self.receiveEval(origin, inStream)
		elif header == headers.HEADER_REPLY:
			self.receiveReply(origin, inStream)
		elif header == headers.HEADER_MESSAGE_ERROR:
			self.receiveMessageError(origin, inStream)
		elif header == headers.HEADER_GENERAL_ERROR:
			self.receiveGeneralError(origin, inStream)
		elif header == headers.HEADER_FILTER_IN:
			self.modifyIOFilterInput(origin, inStream)
		elif header == headers.HEADER_FILTER_OUT:
			self.modifyIOFilterOutput(origin, inStream)
		else:
			raise(DecodingError("Unrecognized header %s"%header))
	
	@asynchronous
	def receiveResolve(self, origin, inStream):
		""" Process a resolution request.
		
		    A resolution request consists of a message ID and a transverse ID.
		    The transverse ID is mapped to the resident shared object ID if it
		    is present, otherwise an error is sent. 
		"""
		# Strip out the message ID for response tagging
		messageID = MessageID.deserialize(inStream)
		
		try:
			# Strip out the transverse object identifier and resolve it
			transverseID = TransverseID.deserialize(inStream)
			reference = self.connection.transverseIDToReference(transverseID)
			
			# Create the response object
			outStream = origin.getOutputBuffer()
			outStream.write(headers.HEADER_REPLY)
			MessageID.serialize(messageID, outStream)
			Reference.serialize(reference, outStream)
			
			# Transmit the response
			outStream.commit()
		
		except Exception as te:
			self.handleIncomingMessageError(origin, messageID, te)
	
	def receiveNotify(self, origin, inStream):
		""" Process a notification.
		
		    A notification is an  evaluation for which there is no return data.
		    The request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized
		    arguments for that function call.
		"""
		#First argument --must-- be a sharedObjectID and local
		call = self.connection.deserializeObject(ExposedCallable, inStream)
		
		# Make the call
		call.handleNotification(self.connection, inStream)
	
	@asynchronous
	def receiveEval(self, origin, inStream):
		""" Process a function-evaluation request.
		
		    An evaluation request consists of a messageID and an objectID (the
		    object must be local and a function/callable), followed by the
		    serialized arguments for that object.
		"""
		# Strip out the message ID for response tagging
		messageID = MessageID.deserialize(inStream)
		
		try:
			#First argument --must-- be an ExposedCallable object
			call = self.connection.deserializeObject(ExposedCallable, inStream)
			# Create the response object
			outStream = origin.getOutputBuffer()
			outStream.write(headers.HEADER_REPLY)
			MessageID.serialize(messageID, outStream)
			
			# Make the call			
			call.handleEval(self.connection, inStream, outStream)
			
			# Send the message
			outStream.commit()
		
		except Exception as te:
			self.handleIncomingMessageError(origin, messageID, te)
	
	def receiveReply(self, origin, inStream):
		""" Process a response to a function evaluation.
		
		    A reply notification consists of the message ID of the original
		    message followed by serialized arguments for the response
		    marshalling code.
		"""
		# Find the response callback and call it on the inStream
		messageID = MessageID.deserialize(inStream)
		doneCall, _ = self.bus.resolveMessageID(messageID, self)
		doneCall(inStream)
	
	def receiveMessageError(self, origin, inStream):
		""" Process an error response to a function evaluation.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    the message ID of the original message followed by an object ID for
		    the exception object.
		"""
		# Find the error callback
		messageID = MessageID.deserialize(inStream)
		_, error = self.bus.resolveMessageID(messageID, self)
		
		# Must be a local Exception object
		exceptionObject = self.connection.deserializeObject(Exception, inStream)
		
		error(exceptionObject)
	
	def receiveGeneralError(self, origin, inStream):
		""" Process an error received as a general failure.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    an object ID for the error function to call.
		"""
		exceptionObject = self.deserializeObject(Exception, inStream)
		
		self.connection.handleReportedRemoteGeneralError(exceptionObject)
	
	def modifyIOFilterInput(self, origin, inStream):
		""" Process the application of a filter to the incoming stream.
		
		    Remote end-point requests that a filter be applied to the incoming
		    data.  This required that the correct filter object be extracted
		    from the local shared object cache and then applied to the stream.
		"""
		# strip out the incoming filter object (must be local)
		filterElement = self.deserializeObject(FilterElement, inStream)
		
		# Apply to the stream to generate a new stream
		filteredStream = io.BytesIO()
		filterElement.transcode(inStream, filteredStream)
		filteredStream.seek(0)
		
		self.handleReceived(origin, filteredStream)
	
	def modifyIOFilterOutput(self, origin, inStream):
		""" Process the addition of a filter on the response path.
		
		    Remote end-point requests that a filter be applied to the response
		    to the incoming message. This requires that processing be shifted to
		    a new gateway which has the appropriate filter pair in place.
		"""
		# strip out the incoming translator pair
		filterElementLocal = self.deserializeObject(FilterElement, inStream)
		filterElementRemoteRef = Referemce.deserialize(inStream)
		subProtocol = ProtocolFilterReply(self, filterElementLocal,
		                                  filterElementRemoteRef)
		subProtocol.handleReceived(origin, inStream)
	
	##
	# Outgoing message routing
	##
	
	def transceiveResolve(self, destination, transverseID):
		""" Request the remote object ID corresponding to a transverse ID.
		
		    Takes a transverse descriptor and gets the appropriate shared
		    object ID from the remote end of the connection. Message is sent out
		    as a resolve request followed by a message ID and a transverse ID.
		    Return is expected as a shared object ID.
		"""
		#TODO: Make caching destination dependent
		#TODO: Make caching dependent on a transport ID from the bus
		fut = Future()
		
		try:
			fut.setResult(self.cachedTransverse[(destination.transport,
			                                     transverseID)])	
			return fut
		except KeyError:
			pass
		
		messageID = self.bus.generateMessageID()
		
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_RESOLVE)
		MessageID.serialize(messageID, outStream)
		TransverseID.serialize(transverseID, outStream)
		
		def reply(inStream):
			try:
				result = Reference.deserialize(inStream)
				self.cachedTransverse[(destination.transport,
				                       transverseID)] = result
				fut.setResult(result)
			except Exception as e:
				fut.setError(e)
		
		
		self.bus.waitForReply(messageID, reply, fut.setError, self)
		outStream.commit()
		return fut
	
	def transmitNotify(self, destination, callRef):
		""" Sends out a notification to the destination, will not except a
		    response from the other end so no message ID is included.
		"""
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_NOTIFY)
		reference.serialize(callRef, outStream)
		return outStream
	
	@asynchronous
	def transceiveEval(self, destination, callID):
		""" Call a remote function and retrieve the reply.
		
		    transceiveEval is responsible for sending out the EVAL message and
		    then waiting for the response from the server. 
		"""
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_EVAL)
		messageID = self.bus.generateMessageID()
		
		MessageID.serialize(messageID, outStream)
		Reference.serialize(callID, outStream)
		
		fut = Future()
		self.bus.waitForReply(messageID, fut.setResult, fut.setError, self)
		return outStream, fut
	
	def transmitMessageError(self, destination, messageID, error):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able
		    to send a transverse error.
		"""
		outStream = self.beginWrite(destination, headers.HEADER_MESSAGE_ERROR)
		MessageID.serialize(messageID, outStream)
		self.connection.serializeObject(error, PassByReference, outStream)
		outStream.commit()
	
	def transmitGeneralError(self, destination, error):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able to send a transverse error.
		"""
		outStream = self.beginPacket(destination, headers.HEADER_GENERAL_ERROR)
		self.connection.serializeObject(error, PassByReference, outStream)
		outStream.commit()
	
	def handleIncomingMessageError(self, destination, messageID, error):
		""" Handler for the situation when an incoming message (an eval or resolve) has
		    triggered an error, such that the error in question should be send as an error
		    reply as a response to the message.
		"""
		print("ERROR")
		print(error)
		if not isinstance(error, TransverseException):
			self.connection.handleLocalException(error)
			if Gateway.debugMode:
				# In debug mode give a stringified version of the error back to the client
				error = SerializedError(repr(error))
			else:
				# any unhandled exceptions will have to be handled locally
				error = UnknownError(error)
		errFuture = error.remoteClone(destination)
		def doSend(fut):
			self.transmitMessageError(destination, messageID, fut.result())
		errFuture.add_done_callback(doSend)
