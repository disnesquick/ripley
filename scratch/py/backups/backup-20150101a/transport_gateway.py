import asyncio
import struct
from util import *
from serialize import *
from errors import *
from shared import *
from transport import TransportClosed
import headers

class ExposedCall:
	def __init__(self, func, iface):
		self.func = func
		self.iface = iface

class TransportGateway:
	#TODO use an UpDict for this
	exposedDefault = [
	   UnknownError,
	   SerializedError,
	   UnknownMessageIDError,
	   UnknownTransverseIDError,
	   UnknownObjectIDError,
	   DecodingError,
	   EncodingError,
	   TransmissionError
	]

	def __init__(self, lineTranscoder, transport, debugMode = False):
		self.transcoder = lineTranscoder
		self.transport = transport
		self.responseWaitingQueue = {}
		self.isOpen = True
		transport.setCallbacks(self.handleNewMessage, self.handleGeneralFailure)
		self.messageCount = -1
		self.destID = transport.portalNegotiation()
		self.debugMode = debugMode
		self.exposedObjects[self.generateShareID] = None

		#TODO this is kludgy
		for exposed in self.exposedDefault:
			self.exposeObjectImplementation(exposed)

	def serverMode(self):
		yield from self.transport.blockUntilClosed()
		self.isOpen = False

	def __del__(self):
		asyncio.get_event_loop().call_soon(self.close)
		
	def close(self):
		""" Closes the transport poling loop by setting the exit flag and causing the transport
		    to unblock and return a NULL action.
		"""
		if self.isOpen:
			self.isOpen = False
			yield from self.transport.hangUp()
			yield from self.serverMode()

	def generateMessageID(self):
		""" Generates a message ID in the form of a byte-string. 
		    Message IDs are based on a simple incrementation counter.
		    TODO: when a sufficient buffer length has passed, reset the message ID counter.
		"""
		self.messageCount += 1
		return SerialID.integersToBytes(self.messageCount)	

	##
	# 
	# Receiving code for transport gateway
	#
	##
	def handleNewMessage(self, byteStream):
		return asyncio.async(self.processReceived(byteStream, self.transport))

	@asyncio.coroutine
	def processReceived(self, byteStream, remoteEndTransport):
		header = byteStream.read(1)
		if header == headers.HEADER_HUP:
			raise(TransportClosed())
		elif header == headers.HEADER_RESOLVE:
			yield from self.receiveResolve(byteStream, remoteEndTransport)
		elif header == headers.HEADER_NOTIFY:
			yield from self.receiveNotify(byteStream, remoteEndTransport)
		elif header == headers.HEADER_EVAL:
			yield from self.receiveEval(byteStream, remoteEndTransport)
		elif header == headers.HEADER_REPLY:
			yield from self.receiveReply(byteStream, remoteEndTransport)
		elif header == headers.HEADER_MESSAGE_ERROR:
			yield from self.receiveMessageError(byteStream, remoteEndTransport)
		elif header == headers.HEADER_GENERAL_ERROR:
			yield from self.receiveGeneralError(byteStream, remoteEndTransport)
		elif header == headers.HEADER_FILTER_IN:
			yield from self.modifyIOFilterInput(byteStream, remoteEndTransport)
		elif header == headers.HEADER_FILTER_OUT:
			yield from self.modifyIOFilterOutput(byteStream, remoteEndTransport)
		else:
			raise(DecodingError("Unrecognized header %s"%header))

	@asyncio.coroutine
	def modifyIOFilterInput(self, byteStream, remoteEndTransport):
		""" Apply a filter to the input stream
		"""
		try:
			# strip out the incoming translator pair
			filterID = self.transcoder.decodeSingle(ObjectID, byteStream)

			filterElement = self.dereferenceSharedSingle(filterID, FilterElement)

			filteredStream = io.BytesIO(filterElement.transcode(byteStream.read()))


		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)
			
		yield from self.processReceived(filteredStream, remoteEndTransport)

	@asyncio.coroutine
	def modifyIOFilterOutput(self, byteStream, remoteEndTransport):
		""" Apply a filter to the output
		"""
		try:
			# strip out the incoming translator pair
			filterID = self.transcoder.decodeSingle(ObjectID, byteStream)
			filterElementCoder = self.dereferenceSharedSingle(filterID, FilterElement)
			filterID = self.transcoder.decodeSingle(ObjectID, byteStream)
			filterElementBundle = self.dereferenceSharedSingle(filterID, FilterElement)
			filteredEndHandle = FilterOutputTransportKludge(filterElementCoder, filterElementBundle, remoteEndTransport, self)

		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)
		yield from self.processReceived(byteStream, remoteEndTransport)

	@asyncio.coroutine
	def receiveResolve(self, byteStream, remoteEndTransport):
		""" Process a resolution request. A resolution request consists of a message ID
		    and a transverse ID. The transverse ID is mapped to the resident shared
		    object ID if it is present, otherwise an error is sent. 
		"""

		# if stripping the response ID fails then the exception should be sent to the general
		# receiver on the other end.
		responseID = None

		try:
			# Strip out the message ID for response tagging
			responseID = self.transcoder.decodeSingle(MessageID, byteStream)

			# Strip out the transverse object identifier
			transverseID = self.transcoder.decodeSingle(TransverseID, byteStream)

			if not transverseID in self.exposedTransverseMap:
				# This gateway does not know about this transverse identifier
				raise (UnknownTransverseIDError(transverseID))
			else:
				# return the exposed object associated with the transverse identifier
				sharedID = self.exposedTransverseMap[transverseID]
				yield from self.transmitReply(remoteEndTransport, responseID, EncodingTypeBinding((sharedID,), (ObjectID,)))

		except DecodingError as te:
			#This is the only point at which we would not have a valid responseID
			if responseID is None:
				yield from self.handleIncomingGeneralError(te, remoteEndTransport)
			else:
				yield from self.handleIncomingMessageError(responseID, te, remoteEndTransport)		

		except Exception as te:
			yield from self.handleIncomingMessageError(responseID, te, remoteEndTransport)

	@asyncio.coroutine
	def receiveNotify(self, byteStream, remoteEndTransport):
		""" Process a notification (An evaluation for which there is no return data).
		    An evaluation request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized arguments
		    for that function call.
		"""
		try:
			#First argument --must-- be a sharedObjectID
			callID = self.transcoder.decodeSingle(ObjectID, byteStream)
			if not callID in self.exposedObjects:
				raise(UnknownObjectIDError(callID))
			else:
				call = self.exposedObjects[callID]

			# Handle the argument marshalling
			args = call.iface.deserializeArguments(self, byteStream)
	
			# Do the function call
			call.func(*args)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)

	@asyncio.coroutine
	def receiveEval(self, byteStream, remoteEndTransport):
		""" Process a function-evaluation request. An evaluation request consists of a
		    message ID and an object ID (the object must be local and a function/callable),
		    followed by the serialized arguments for that object.
		"""
		# if stripping the response ID fails then the exception should be sent to the general
		# receiver on the other end.
		responseID = None

		try:
			# Strip out the message ID for response tagging
			responseID = self.transcoder.decodeSingle(MessageID, byteStream)

			#First argument --must-- be a sharedObjectID
			callID = self.transcoder.decodeSingle(ObjectID, byteStream)
			if not callID in self.exposedObjects:
				raise(UnknownObjectIDError(callID))
			else:
				call = self.exposedObjects[callID]

			# Handle the argument marshalling
			args = call.iface.deserializeArguments(self, byteStream)

			# Do the function call
			returnData = call.func(*args)

			# Finally, bind the returned data and send it as a response
			boundReturn = call.iface.bindResponseSerialization(self, returnData)

			yield from self.transmitReply(remoteEndTransport, responseID, boundReturn)

		except DecodingError as te:
			#This is the only point at which we would not have a valid responseID
			if responseID is None:
				yield from self.handleIncomingGeneralError(te, remoteEndTransport)
			else:
				yield from self.handleIncomingMessageError(responseID, te, remoteEndTransport)		

		except Exception as te:
			yield from self.handleIncomingMessageError(responseID, te, remoteEndTransport)

	@asyncio.coroutine
	def receiveReply(self, byteStream, remoteEndTransport):
		""" Process a response to a function evaluation. A reply notification consists of
		    the message ID of the original message followed by serialized arguments for
		    the response marshalling code.
		"""
		try:
			# Strip out the message ID for response tagging
			replyToMessageID = self.transcoder.decodeSingle(MessageID, byteStream)
        	
			# Ensure that the message is a response to a message from this gateway
			if not replyToMessageID in self.responseWaitingQueue:
				# send a general error to the other-side if this message was unknown
				raise(UnknownMessageIDError(replyToMessageID))

			# Grab the future and return argument binder
			resolve, _ = self.responseWaitingQueue.pop(replyToMessageID)

			resolve(byteStream)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)

	@asyncio.coroutine
	def receiveMessageError(self, byteStream, remoteEndTransport):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		"""
		try:
			# Strip out the message ID for response tagging
			replyToMessageID = self.transcoder.decodeSingle(MessageID, byteStream)
        	
			# Ensure that the message is a response to a message from this gateway
			if not replyToMessageID in self.responseWaitingQueue:
				# send a general error to the other-side if this message was unknown
				raise(UnknownMessageIDError(replyToMessageID))
			
			# Grab the future but discard the return binder
			_, error = self.responseWaitingQueue.pop(replyToMessageID)

			# First argument --must-- be a sharedObjectID and a function
			callID = self.transcoder.decodeSingle(ObjectID, byteStream)
			if not callID in self.exposedObjects:
				raise(UnknownObjectIDError(callID))
			else:
				call = self.exposedObjects[callID]

			# Handle the argument marshalling
			args = call.iface.deserializeArguments(self, byteStream)

			# Do the function call
			returnData = call.func(*args)

			# Ensure that the function does actually return a valid exception
			if not isinstance(returnData, Exception):
				raise(ObjectIsNotExceptionError(callID))
			
			error(returnData)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)

	@asyncio.coroutine
	def receiveGeneralError(self, byteStream, remoteEndTransport):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		"""
		try:
			# First argument --must-- be a sharedObjectID and a function
			callID = self.transcoder.decodeSingle(ObjectID, byteStream)
			if not callID in self.exposedObjects:
				raise(UnknownObjectIDError(callID))
			else:
				call = self.exposedObjects[callID]

			# Handle the argument marshalling
			args = call.iface.deserializeArguments(self, byteStream)
	
			# Do the function call
			returnData = call.func(*args)

			# Ensure that the function does actually return a valid exception
			if not isinstance(returnData, Exception):
				raise(ObjectIsNotExceptionError(callID))
			
			self.handleReportedRemoteGeneralError(returnData, remoteEndTransport)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te, remoteEndTransport)

	##
	# 
	# Sending code for transport gateway
	#
	##

	@asyncio.coroutine
	def transceiveResolve(self, obj):
		""" Takes a transverse descriptor and gets the appropriate shared object ID from the remote
		    end of the connection. Message is sent out as a resolve request followed by a message ID
		    and a transverse ID. Return is expected as a shared object ID.
		"""
		messageID = self.generateMessageID()

		outStream = self.transport.beginWrite(headers.HEADER_RESOLVE)
		self.transcoder.encodeSingle(MessageID, messageID, outStream)
		self.transcoder.encodeSingle(TransverseID, obj.__transverse_id__, outStream)

		waiter = self.waitOnReply(messageID, lambda _, obj : self.transcoder.decodeSingle(ObjectID, obj))
		yield from self.transport.commitWrite(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitNotify(self, callID, boundArgs):
		""" Sends out a notification to the destination, will not except a response from the other
		    end so no message ID is included.
		"""
		outStream = self.transport.beginWrite(headers.HEADER_NOTIFY)
		self.transcoder.encodeSingle(ObjectID, callID, outStream)
		self.transcoder.encode(boundArgs, outStream)

		yield from self.transport.commitWrite(outStream)

	@asyncio.coroutine
	def transceiveEval(self, callID, boundArgs, returnDecoder):
		""" transceiveEval is responsible for sending out the EVAL message and then waiting
		    for the response from the server. 
		"""
		outStream = self.transport.beginWrite(headers.HEADER_EVAL)
		messageID = self.generateMessageID()

		self.transcoder.encodeSingle(MessageID, messageID, outStream)
		self.transcoder.encodeSingle(ObjectID, callID, outStream)
		self.transcoder.encode(boundArgs, outStream)

		waiter = self.waitOnReply(messageID, returnDecoder)

		yield from self.transport.commitWrite(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitReply(self, responseTransport, responseID, boundReply):
		""" transmitReply is responsible for sending out the response to a received message
		    it is only used internally by receiveEval and receiveResolve.
		"""
		outStream = responseTransport.beginWrite(headers.HEADER_REPLY)
		self.transcoder.encodeSingle(MessageID, responseID, outStream)
		self.transcoder.encode(boundReply, outStream)

		yield from responseTransport.commitWrite(outStream)

	@asyncio.coroutine
	def transmitMessageError(self, responseTransport, responseID, errorID, boundArgs):
		""" Send a TransverseException object down the wire as an error.
		    This function is called internally and so will only be able to send a transverse error.
		"""
		outStream = responseTransport.beginWrite(headers.HEADER_MESSAGE_ERROR)
		self.transcoder.encodeSingle(MessageID, responseID, outStream)
		self.transcoder.encodeSingle(ObjectID, errorID, outStream)
		self.transcoder.encode(boundArgs, outStream)

		yield from responseTransport.commitWrite(outStream)

	@asyncio.coroutine
	def transmitGeneralError(self, responseTransport, errorID, boundArgs):
		""" Send a TransverseException object down the wire as an error.
		    This function is called internally and so will only be able to send a transverse error.
		"""
		outStream = responseTransport.beginWrite(headers.HEADER_GENERAL_ERROR)
		self.transcoder.encodeSingle(ObjectID, errorID, outStream)
		self.transcoder.encode(boundArgs, outStream)

		yield from responseTransport.commitWrite(outStream)


	##
	# 
	# General auxilliary functions for transmitting/transceiving
	#
	##
	def waitOnReply(self, messageID, decoder):
		""" Sets up a future which will be activated when the response to the outgoing message
		    comes in.
		""" 
		waiter = asyncio.Future()
		def resolve(byteStream):
			# Handle the argument marshalling
			response = decoder(self, byteStream)

			# Decode single items from list wrapper
			if len(response) == 1:
				response = response[0]
			waiter.set_result(response)

		self.responseWaitingQueue[messageID] = resolve, waiter.set_exception
		return waiter


	@asyncio.coroutine
	def resolveTransverse(self, obj):
		""" Searches the local identity map for the transverse identifier. If it exists
		    then return that shared object ID. If it does not exist then the object
		    is request from the bus and cached in the local identity map before it is
		    returned.
		"""
		ident = obj.__transverse_id__
		if not ident in self.remoteTransverseMap:
			self.remoteTransverseMap[ident] = (yield from self.transceiveResolve(obj))

		return self.remoteTransverseMap[ident]

	##
	#
	# Default error handling
	#
	##

	def handleGeneralFailure(self, error):
		""" If everything else fails then call this function as a final resort
		    Its job is to clean up the connection (i.e. cleanly disengage from the
		    bus and then report a complete and final failure to the outer code.
		"""
		asyncio.get_event_loop().call_soon(self.close)
		raise(error)

	def handleFatalRemoteFailure(self, error, remoteEndTransport):
		""" When shit is so fucked up on the remote end that there is no way
		    to recover, the local end needs to gracefully disconnect or ignore that
		    remote peer.
		"""
		yield from self.close()
		raise(RemoteEndFailure(error, remoteEndTransport))
	
	def handleIncomingMessageError(self, messageID, error, remoteEndTransport):
		""" Handler for the situation when an incoming message (an eval or resolve) has
		    triggered an error, such that the error in question should be send as an error
		    reply as a response to the message.
		"""
		if not isinstance(error, TransverseException):
			if self.debugMode:
				# In debug mode give a stringified version of the error back to the client
				yield from self.handleIncomingMessageError(messageID, SerializedError(repr(error)), remoteEndTransport)
			else:
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				yield from self.handleIncomingMessageError(messageID, UnknownError(), remoteEndTransport)
		else:
			try:
				errorID = (yield from self.resolveTransverse(error.__iface_members__["__constructor__"]))
				yield from self.transmitMessageError(remoteEndTransport, messageID, errorID, error.getBoundArgs(self))
			except Exception as err:
				yield from self.handleFatalRemoteFailure(err, remoteEndTransport)
	
	def handleIncomingGeneralError(self, error, remoteEndTransport):
		""" Handler for the situation when when an incoming notification (notify, reply, error)
		    has triggered an error and there is therefore no specific message to append the
		    error-response to so it should just be reported as a general error.
		"""
		if not isinstance(error, TransverseException):
			if self.debugMode:
				# In debug mode give a stringified version of the error back to the client
				yield from self.handleIncomingGeneralError(SerializedError(repr(error)), remoteEndTransport)
			else:
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				yield from self.handleIncomingGeneralError(UnknownError(), remoteEndTransport)
		else:
			try:
				errorID = (yield from self.resolveTransverse(error.__iface_members__["__constructor__"]))
				yield from self.transmitGeneralError(remoteEndTransport, errorID, error.getBoundArgs(self))
			except Exception as err:
				yield from self.handleFatalRemoteFailure(err, remoteEndTransport)

	def handleReportedRemoteGeneralError(self, error, remoteEndTransport):
		""" Local side of handleIncomingGeneralError: The remote side reports that the local side
		    has caused an error non-specific to any IDed message.
		"""
		raise(error)

