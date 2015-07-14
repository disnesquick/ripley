""" Module: connection
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file defines a single class, `Connection'. See the comments of that
    class for further details.
"""

# External imports
from unstuck import *

# Local imports
from .          import headers
from .serialize import *
from .service   import *
#from .errors    import *
from .filter    import *

# Exports
__all__ = ["Connection"]


class TransverseException:
	pass

class Connection:
	""" This class reifies an encapsulated process on a Bus.
	
	    This class handles the mapping of object IDs to and from objects. It
	    also handles the exposure of objects through transverse identifiers.
	    Finally it contains the processing methods for handling incoming binary
	    message streams and the calling of appropriate local methods
	"""
	def __init__(self, bus, connectionID):
		# Object brokering
		self.objectToObjectID = {}
		self.objectIDToObject = {}
		self.objectCount = -1
		self.transverseMaps = []
		self.proxyTokens = {}
		
		# Connection to bus
		self.bus = bus
		self.connectionID = connectionID
		
		# Transverse caching
		self.cachedTransverse = {}
	
	def handleLocalException(self, error):
		raise error
	
	##
	# Code for handling object caching
	##
	
	def generateObjectID(self):
		""" Generates an object ID in the form of a SerialID.
		
		    Referencess are transfered in the form of a connection-specific
		    unique identifier plus an identifier for the connection itself.
		    However, this connectionID is handled elsewhere.
		"""
		self.objectCount += 1
		return SerialID.integerToBytes(self.objectCount)
	
	def objectToReference(self, obj):
		""" Obtains a reference identifier for an object.
		
		    If the object has been shared previously then the previous reference
		    is returned, otherwise a reference is generated and marked against
		    the object.  The connection ID is added for local objects to create
		    a complete reference.
		"""
		if isinstance(obj, ObjectProxy):
			return obj.reference
		
		if obj in self.objectToObjectID:
			objectID = self.objectToObjectID[obj]
		else:
			# This is a new object so generate the reference and store them
			objectID = self.generateObjectID()
			self.objectIDToObject[objectID] = obj
			self.objectToObjectID[obj] = objectID
			
		return self.connectionID, objectID
	
	def referenceToObject(self, reference, typ):
		""" Maps an incoming object reference to a python object.
		
		    Local objects will be mapped to their local python object whereas
		    remote objects will be wrapped in an object proxy.
		"""
		connectionID, objectID = reference
		
		if connectionID == self.connectionID:
			if not objectID in self.objectIDToObject:
				raise(UnknownObjectIDError(objectID))
			obj = self.objectIDToObject[objectID]
			if not isinstance(obj, typ):
				raise(TypeMismatchError(type(obj), typ))
		else:
			try:
				destination = self.proxyTokens[connectionID]
			except:
				raise(UnknownReferenceError(reference))
			obj = typ.getProxyClass()(destination, reference)
		return obj
	
	def serializeObject(self, obj, outStream):
		""" Serializes a PassByReference object.
		
		    This function obtains a reference to the supplied object and writes
		    it to the outputStream. No type checking is performed.
		"""
		ref = self.objectToReference(obj)
		Reference.serialize(ref, outStream)
	
	def deserializeObject(self, inStream, typeCheck):
		""" Deserializes and type-checked a single PassByReference object.
		
		    This function deserializes a reference from inStream and matches
		    it to an object in the local cache (or creates a proxy object).
		    Type checking on local objects is performed to prevent spoofing.
		"""
		ref = Reference.deserialize(inStream)
		return self.referenceToObject(ref, typeCheck)
	
	##
	# Function related to transverse object resolution
	##
	
	def addTransverseMap(self, transverseMap):
		""" Adds a dictionary of transverse mappings to the Connection.
		
		    This method is usually applied when a ServiceImplementatiob object
		    is offered on a Connection. The list of TransverseID -> Object
		    mappings is added to this Connection so that future transverse
		    resolutions will return the objects in question (or rather, the
		    references to them).
		"""
		self.transverseMaps.append(transverseMap)
	
	def transverseIDToReference(self, transverseID):
		""" Maps a TransverseID to a Reference to the appropriate object.
		
		    Looks through the handled transvese maps to find the object
		    corresponding to the TransverseID supplied and then maps the object
		    to a Reference, for transmission over the wire.
		"""
		obj = self.transverseIDToObject(transverseID)
		ref = self.objectToReference(obj)
		return ref
	
	def transverseIDToObject(self, transverseID):
		""" Maps a TransverseID to the appropriate object.
		
		    Looks through the handled transvese maps to find the object
		    corresponding to the TransverseID supplied.
		"""
		for transverseMap in self.transverseMaps:
			try:
				obj = transverseMap[transverseID]
				return obj
			except KeyError:
				pass
		raise(UnknownTransverseIDError(transverseID))
	
	##
	# Incoming message routing
	##
	
	def handleReceived(self, origin, inStream):
		""" Processes the current waiting packet from inStream.
		
		    This procedure retrieves a message packet from inStream and acts
		    according to the header byte received (the first byte read) to pass
		    further processing to the appropriate subprocedure.
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
			reference = self.transverseIDToReference(transverseID)
			
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
		call = self.deserializeObject(inStream, ExposedCall)
		
		# Make the call
		call(self, inStream)
	
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
			call = self.deserializeObject(inStream, ExposedCall)
			# Create the response object
			outStream = origin.getOutputBuffer()
			outStream.write(headers.HEADER_REPLY)
			MessageID.serialize(messageID, outStream)
			
			# Make the call			
			call(self, inStream, outStream)
			
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
		doneCall, _ = self.bus.resolveMessageID(messageID, origin.lastRoute)
		doneCall(inStream)
	
	def receiveMessageError(self, origin, inStream):
		""" Process an error response to a function evaluation.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    the message ID of the original message followed by an object ID for
		    the exception object.
		"""
		# Find the error callback
		messageID = MessageID.deserialize(inStream)
		_, error = self.bus.resolveMessageID(messageID, origin.lastRoute)
		
		transverseID = TransverseID.deserialize(inStream)
		try:
			obj = self.transverseIDToObject(transverseID)
			exceptionObject = obj.handleFetch(self, inStream)
			error(exceptionObject)
		except:
			error(ErrorUnsupported(transverseID))
	
	def receiveGeneralError(self, origin, inStream):
		""" Process an error received as a general failure.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    an object ID for the error function to call.
		"""
		transverseID = TransverseID.deserialize(inStream)
		try:
			obj = self.transverseIDToObject(transverseID)
			exceptionObject = obj.handleFetch(self, inStream)
			error(exceptionObject)
		except:
			error(ErrorUnsupported(transverseID))
		self.bus.handleGeneralError(origin, exceptionObject)
	
	def modifyIOFilterInput(self, origin, inStream):
		""" Process the application of a filter to the incoming stream.
		
		    Remote end-point requests that a filter be applied to the incoming
		    data.  This required that the correct filter object be extracted
		    from the local shared object cache and then applied to the stream.
		"""
		# strip out the incoming filter object (must be local)
		filterElement = self.deserializeObject(inStream, FilterElement)
		
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
		filterElementLocal = self.deserializeObject(inStream, FilterElement)
		filterElementRemoteRef = Reference.deserialize(inStream)
		subOrigin = FilteredResponseRoute(origin, filterElementLocal,
		                                  filterElementRemoteRef)
		self.handleReceived(subOrigin, inStream)
	
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
		fut = Future()
		
		cacheID = destination.transport.remoteBusID, transverseID
		try:
			fut.setResult(self.cachedTransverse[cacheID])	
			return fut
		except KeyError:
			pass
		
		# Create the response listener for the remote resolution.
		def reply(inStream):
			try:
				resolved = Reference.deserialize(inStream)
				self.cachedTransverse[cacheID] = resolved
				fut.setResult(resolved)
			except Exception as e:
				fut.setError(e)
		
		messageID = self.bus.waitForReply(reply, fut.setError,
		                                  destination.lastRoute)
		
		# Format the outgoing message to the wire
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_RESOLVE)
		MessageID.serialize(messageID, outStream)
		TransverseID.serialize(transverseID, outStream)
		outStream.commit()
		
		return fut
	
	def transmitNotify(self, destination, callID):
		""" Call a remote function without any response.
		
		    This function prepares an output stream connected to the destination
		    Route provided. The message type will be tagged as a notification so
		    no reply is expected.
		"""
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_NOTIFY)
		Reference.serialize(callID, outStream)
		return outStream
	
	def transceiveEval(self, destination, callID):
		""" Call a remote function and retrieve the reply.
		
		    transceiveEval is responsible for sending out the EVAL message and
		    then waiting for the response from the server. 
		"""
		fut = Future()
		messageID = self.bus.waitForReply(fut.setResult, fut.setError,
		                                  destination.lastRoute)
		
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_EVAL)
		MessageID.serialize(messageID, outStream)
		Reference.serialize(callID, outStream)
		
		return outStream, fut
	
	def transmitMessageError(self, destination, messageID, error):
		""" Transmit an exception to a destination as a message response.
		
		    This method is used to serialize a TransverseException as a response
		    to a failed evaluation or resolution request.
		"""
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_MESSAGE_ERROR)
		MessageID.serialize(messageID, outStream)
		error.serializeConstructor(self, outStream)
		outStream.commit()
	
	def transmitGeneralError(self, destination, error):
		""" Transmit an exception to a destination.
		
		    This method is probably not ever useful. It is used to signal a
		    general fault on the remote connection. Since even the most insecure
		    public server will want to ignore such Exception, due to the high
		    potential for abuse, this would probably be used on a client where
		    the server is fully trusted.
		"""
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_GENERAL_ERROR)
		error.serializeConstructor(self, outStream)
		outStream.commit()
	
	##
	# Error handling
	##
	
	def handleIncomingMessageError(self, destination, messageID, error):
		""" Handler for an Exception raised on an incoming Eval/Resolve.
		
		    Handler for the situation when an incoming message (an eval or
		    resolve) has triggered an error, such that the error in question
		    should be sent as an error reply as a response to the message.
		"""
		if not isinstance(error, TransverseException):
			self.bus.handleLocalException(destination, error)
		else:
			self.transmitMessageError(destination, messageID, error)
