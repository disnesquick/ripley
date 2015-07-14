import asyncio
import struct
from serialize import *
from errors import *
from shared import *
from transport import TransportClosed
import headers

class Gateway:
	""" Gateway is the 'face' of a route, which handles message preparation, passing, parsing and
	    decoding. A route takes care of object exposure but the gateway takes care of the actual
	    low-level stuff not part of the transport itself. Gateways can be filtered, which adds
	    in another layer of de/encoding.
	"""
	debugMode = False
	def __init__(self, route):
		self.route = route

	def sendFilter(self, localElement, remoteElement):
		""" Apply a filter pair to the outgoing message streams going through this gateway.
		    a new GatewayFilterSend is created and returned with the current filter as its
		    parent.
		"""
		return GatewayFilterSend(self, localElement, remoteElement)

	def replyFilter(self, localElement, remoteElement):
		""" Apply a filter pair to the return path of outgoing message streams going through this
		    gateway. A new GatewayFilterReply is created and returned with the current filter as
		    its parent.
		"""
		return GatewayFilterReply(self, localElement, remoteElement)

	def activateListener(self):
		""" Sets up a server coroutine which will continuously pole the route and handle
		    incoming messages.
		"""
		recvCoro = asyncio.async(self.route.poleTransport(self.handleReceived, self.handleGeneralFailure))
		recvCoro.add_done_callback(lambda fut: fut.result())
		return recvCoro

	##
	# Operations for preparing and transmitting a packet
	##

	def beginPacket(self, header):
		""" Returns a valid output buffer to write to. As a root gateway then
		    the buffer will be the final raw buffer provided by the route.
		"""
		buf = self.route.getBuffer()
		buf.write(header)
		return buf

	@asyncio.coroutine
	def commitPacket(self, inputStream):
		""" Commits a packet to the route, to be sent down the wire.
		"""
		yield from self.route.flushBuffer(inputStream)

	##
	# Functions related to transverse object resolution
	##

	@asyncio.coroutine
	def resolveTransverse(self, transverseID):
		""" Searches the local identity map for the transverse identifier. If it exists
		    then return that shared object ID. If it does not exist then the object
		    is request from the bus and cached in the local identity map before it is
		    returned.
		"""
		try:
			return self.route.getCachedTransverse(transverseID)
		except KeyError:
			objectID = (yield from self.transceiveResolve(transverseID))
			self.route.cacheTransverse(transverseID, objectID)
			return objectID

	##
	# Transcoding functions
	##

	def serializeObjects(self, objs, objTypes, outStream):
		""" Serializes a list of objects objs according to the types in the congruent list
		    objTypes.
		"""	
		for obj, typ in zip(objs, objTypes):
			self.serializeObject(obj, typ, outStream)

	def serializeObject(self, obj, typ, outStream):
		if issubclass(typ, ComplexPassByValue):
			typ.serialize(obj, self, outStream)
		elif issubclass(typ, PassByReference):
			if isinstance(obj, RemoteCall):
				outStream.write(b"\x00"+headers.HEADER_EVAL)
				self.serializeTransverseReference(obj.iface, outStream)
				obj.serializeArguments(self, outStream)
			else:
				ref = self.route.referenceObject(obj)
				ObjectID.serialize(ref, outStream)
		else:
			typ.serialize(obj, outStream)

	def serializeTransverseReference(self, transverse, outStream):
		transverseID = transverse.__transverse_id__
		try:
			# Try and pass the shared reference if it has already been been cached, otherwise
			# send the transverseID.
			# TODO send a subsequent request to cache the transverseID. Use a work stack for this
			ref = self.route.getCachedTransverse(transverseID)
			ObjectID.serialize(ref, outStream)
		except KeyError:
			def reply(gateway, inStream):
				objectID = ObjectID.deserialize(inStream)
				self.route.cacheTransverse(transverseID, objectID)
			messageID = self.route.generateMessageID()
			outStream.write(b"\x00"+headers.HEADER_RESOLVE)
			MessageID.serialize(messageID, outStream)
			waiter = asyncio.async(self.route.waitForReply(messageID, self, reply))
			TransverseID.serialize(transverseID, outStream)
	
	def deserializeObjects(self, objTypes, inStream):
		return tuple(self.deserializeObject(typ, inStream) for typ in objTypes)

	def deserializeObject(self, typ, inStream):
		if issubclass(typ, ComplexPassByValue):
			return typ.deserialize(self, inStream)
		elif issubclass(typ, PassByReference):
			ref = ObjectID.deserialize(inStream)
			if ref[0] == b"\x00":
				if ref[1] == headers.HEADER_RESOLVE:
					messageID = MessageID.deserialize(inStream)
					tref = TransverseID.deserialize(inStream)
					ref = self.route.resolveTransverseID(tref)
					asyncio.async(self.transmitReply(messageID, ref, ObjectID))
					return self.route.dereferenceObject(ref, typ, self)
				elif ref[1] == headers.HEADER_EVAL:
					call = self.deserializeObject(ExposedCallable, inStream)
					args = self.deserializeObjects(call.iface.parameterTypes, inStream)
					obj = call.func(*args)
					if not isinstance(obj, typ):
						raise(ReferenceTypeMismatchError(type(obj), typ))
					return obj	
			else:
				return self.route.dereferenceObject(ref, typ, self)
		else:
			return typ.deserialize(inStream)

	##
	# Incoming message routing
	##

	@asyncio.coroutine
	def handleReceived(self, inStream):
		""" Processes the current waiting packet from inStream and acts according
		    to the header byte received as the first byte read.
		"""
		header = inStream.read(1)
		if header == headers.HEADER_HUP:
			raise(TransportClosed())
		elif header == headers.HEADER_RESOLVE:
			yield from self.receiveResolve(inStream)
		elif header == headers.HEADER_NOTIFY:
			yield from self.receiveNotify(inStream)
		elif header == headers.HEADER_EVAL:
			yield from self.receiveEval(inStream)
		elif header == headers.HEADER_REPLY:
			yield from self.receiveReply(inStream)
		elif header == headers.HEADER_MESSAGE_ERROR:
			yield from self.receiveMessageError(inStream)
		elif header == headers.HEADER_GENERAL_ERROR:
			yield from self.receiveGeneralError(inStream)
		elif header == headers.HEADER_FILTER_IN:
			yield from self.modifyIOFilterInput(inStream)
		elif header == headers.HEADER_FILTER_OUT:
			yield from self.modifyIOFilterOutput(inStream)
		else:
			raise(DecodingError("Unrecognized header %s"%header))

	@asyncio.coroutine
	def receiveResolve(self, inStream):
		""" Process a resolution request. A resolution request consists of a message ID
		    and a transverse ID. The transverse ID is mapped to the resident shared
		    object ID if it is present, otherwise an error is sent. 
		"""
		# if stripping the response ID fails then the exception should be sent to the
		# general receiver on the other end.
		messageID = None

		try:
			# Strip out the message ID for response tagging
			messageID = MessageID.deserialize(inStream)

			# Strip out the transverse object identifier and resolve it
			transverseID = TransverseID.deserialize(inStream)
			sharedID = self.route.resolveTransverseID(transverseID)

			# Send the response down the wire
			yield from self.transmitReply(messageID, sharedID, ObjectID)
		except Exception as te:
			#This is the only point at which we would not have a valid responseID
			if messageID is None:
				yield from self.handleIncomingGeneralError(te)
			else:
				yield from self.handleIncomingMessageError(messageID, te)

	@asyncio.coroutine
	def receiveNotify(self, inStream):
		""" Process a notification (An evaluation for which there is no return data).
		    An evaluation request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized arguments
		    for that function call.
		"""
		try:
			#First argument --must-- be a sharedObjectID and local
			call = self.deserializeObject(ExposedCallable, inStream)

			# Handle the argument marshalling
			args = self.deserializeObjects(call.iface.parameterTypes, inStream)
	
			# Do the function call
			call.func(*args)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveEval(self, inStream):
		""" Process a function-evaluation request. An evaluation request consists of a
		    messageID and an objectID (the object must be local and a function/callable),
		    followed by the serialized arguments for that object.
		"""
		# if stripping the response ID fails then the exception should be sent to the
		# general receiver on the other end.
		messageID = None

		try:
			# Strip out the message ID for response tagging
			messageID = MessageID.deserialize(inStream)

			#First argument --must-- be an ExposedCallable object
			call = self.deserializeObject(ExposedCallable, inStream)
	
			# Handle the argument marshalling
			args = self.deserializeObjects(call.iface.parameterTypes, inStream)

			# Do the function call
			returnData = call.func(*args)

			# Finally, bind the returned data and send it as a response
			yield from self.transmitReply(messageID, returnData, call.iface.returnType)

		except Exception as te:
			#This is the only point at which we would not have a valid responseID
			if messageID is None:
				yield from self.handleIncomingGeneralError(te)
			else:
				yield from self.handleIncomingMessageError(messageID, te)

	@asyncio.coroutine
	def receiveReply(self, inStream):
		""" Process a response to a function evaluation. A reply notification consists of
		    the message ID of the original message followed by serialized arguments for
		    the response marshalling code.
		"""
		try:
			# Find the response callback and call it on the inStream
			messageID = MessageID.deserialize(inStream)
			resolve, error = self.route.resolveMessageID(messageID)
			try:
				resolve(inStream)
			except Exception as e:
				error(e)
		except Exception as te:
			# Exceptions have to be sent as general exceptions
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveMessageError(self, inStream):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the exception object.
		"""
		try:
			# Find the error callback
			messageID = MessageID.deserialize(inStream)
			_, error = self.route.resolveMessageID(messageID)

			exceptionObject = self.deserializeObject(TransverseExceptionInterface, inStream)
			if isinstance(exceptionObject, ProxyObject):
				raise(NonLocalReference(exceptionObject.__shared_id__))

			error(exceptionObject)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveGeneralError(self, inStream):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		"""
		try:
			exceptionObject = self.deserializeObject(TransverseExceptionInterface, inStream)
			if isinstance(exceptionObject, ProxyObject):
				raise(NonLocalReference(exceptionObject.__shared_id__))

			self.handleReportedRemoteGeneralError(exceptionObject)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def modifyIOFilterInput(self, inStream):
		""" Remote end-point requests that a filter be applied to the incoming data.
		    This required that the correct filter object be extracted from the local
		    shared object cache and then applied to the stream.
		"""
		try:
			# strip out the incoming filter object
			filterElement = self.deserializeObject(FilterElement, inStream)
			if isinstance(filterElement, ProxyObject):
				raise(NonLocalReference(filterElement.__shared_id__))

			# Apply to the stream to generate a new stream
			filteredStream = io.BytesIO()
			filterElement.transcode(inStream, filteredStream)
			filteredStream.seek(0)

			yield from self.handleReceived(filteredStream)
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def modifyIOFilterOutput(self, inStream):
		""" Remote end-point requests that a filter be applied to the response to the
		    incoming message. This requires that processing be shifted to a new
		    gateway which has the appropriate filter pair in place.
		"""
		try:
			# strip out the incoming translator pair
			filterElementLocal = self.deserializeObject(FilterElement, inStream)
			if isinstance(filterElementLocal, ProxyObject):
				raise(NonLocalReference(filterElementLocal.__shared_id__))
			filterElementRemote = self.deserializeObject(FilterElement, inStream)
			subGateway = self.sendFilter(filterElementLocal, filterElementRemote)
			yield from subGateway.handleReceived(inStream)

		except Exception as te:
			yield from self.handleIncomingGeneralError(te)


	##
	# Outgoing message routing
	##

	@asyncio.coroutine
	def transceiveResolve(self, transverseID):
		""" Takes a transverse descriptor and gets the appropriate shared object ID from
		    the remote end of the connection. Message is sent out as a resolve request
		    followed by a message ID and a transverse ID. Return is expected as a shared
		    object ID.
		"""
		def reply(gateway, inStream):
			return ObjectID.deserialize(inStream)

		messageID = self.route.generateMessageID()

		outStream = self.beginPacket(headers.HEADER_RESOLVE)
		MessageID.serialize(messageID, outStream)
		TransverseID.serialize(transverseID, outStream)

		waiter = self.route.waitForReply(messageID, self, reply)
		yield from self.commitPacket(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitNotify(self, callID, writeArgs):
		""" Sends out a notification to the destination, will not except a response from
		    the other end so no message ID is included.
		"""
		outStream = self.beginPacket(headers.HEADER_NOTIFY)
		ObjectID.serialize(callID, outStream)
		writeArgs(self, outStream)

		yield from self.commitPacket(outStream)
	
	@asyncio.coroutine
	def transceiveEval(self, callID, writeArgs, readReply):
		""" transceiveEval is responsible for sending out the EVAL message and then
		    waiting for the response from the server. 
		"""
		outStream = self.beginPacket(headers.HEADER_EVAL)
		messageID = self.route.generateMessageID()

		MessageID.serialize(messageID, outStream)
		ObjectID.serialize(callID, outStream)
		writeArgs(self, outStream)
		waiter = self.route.waitForReply(messageID, self, readReply)

		yield from self.commitPacket(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitReply(self, messageID, arg, argType):
		""" transmitReply is responsible for sending out the response to a received message
		    it is only used internally by receiveEval and receiveResolve.
		"""
		outStream = self.beginPacket(headers.HEADER_REPLY)
		MessageID.serialize(messageID, outStream)
		self.serializeObject(arg, argType, outStream)

		yield from self.commitPacket(outStream)

	@asyncio.coroutine
	def transmitMessageError(self, messageID, error):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able to send a transverse error.
		"""
		outStream = self.beginPacket(headers.HEADER_MESSAGE_ERROR)
		MessageID.serialize(messageID, outStream)
		self.serializeObject(error, PassByReference, outStream)

		yield from self.commitPacket(outStream)

	@asyncio.coroutine
	def transmitGeneralError(self, error):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able to send a transverse error.
		"""
		outStream = self.beginPacket(headers.HEADER_GENERAL_ERROR)
		self.serializeObject(error, PassByReference, outStream)

		yield from self.commitPacket(outStream)

	##
	# Error handling functions
	##
	@asyncio.coroutine
	def handleIncomingMessageError(self, messageID, error):
		""" Handler for the situation when an incoming message (an eval or resolve) has
		    triggered an error, such that the error in question should be send as an error
		    reply as a response to the message.
		"""
		if isinstance(error, TransverseException):
			yield from self.transmitMessageError(messageID, error.remoteClone())
		else:
			if Gateway.debugMode:
				# In debug mode give a stringified version of the error back to the client
				serialError = SerializedError(repr(error))
				yield from self.handleIncomingMessageError(messageID, serialError)
			else:
				# any unhandled exceptions will have to be handled locally
				self.handleLocalException(error)
	
	@asyncio.coroutine
	def handleIncomingGeneralError(self, error):
		""" Handler for the situation when when an incoming notification (notify, reply, error)
		    has triggered an error and there is therefore no specific message to append the
		    error-response to so it should just be reported as a general error.
		"""
		if isinstance(error, TransverseException):
			yield from self.transmitGeneralError(error.remoteClone)
		else:
			if Gateway.debugMode:
				# In debug mode give a stringified version of the error back to the client
				serialError = SerializedError(repr(error))
				yield from self.handleIncomingGeneralError(serialError)
			else:
				# any unhandled exceptions will have to be handled locally
				self.handleLocalException(error)
	
	def handleReportedRemoteGeneralError(self, error):
		""" Local side of handleIncomingGeneralError: The remote side reports that the local side
		    has caused an error non-specific to any IDed message.
		"""
		raise(error)

	def handleLocalException(self, error):
		""" There was a problem with the local code which should not be passed on to the other
		    side. This function should be over-ridden by inheritance, normally.
		"""
		raise(error)

	def handleGeneralFailure(self, error):
		""" If everything else fails then call this function as a final resort
		    Its job is to clean up the connection (i.e. cleanly disengage from the
		    bus and then report a complete and final failure to the outer code.
		"""
		asyncio.get_event_loop().run_until_complete(self.route.close())
		raise(error)


class GatewayFilter(Gateway):
	""" Base class for Gateways with a filter element pair active on it, used for testing
	    whether to apply filters or not.
	"""
	def __init__(self, parent, localElement, remoteElement):
		super().__init__(parent.route)
		self.parent = parent
		self.localElement = localElement
		self.remoteElement = remoteElement

	def beginPacket(self, header):
		""" Returns a valid output buffer to write to. As a filter gateway, 
		    the buffer will be a temporary buffer that can be modified by the filter.
		"""
		# TODO if this is the final cluster of reply filters then a temporary buffer
		# is not actually needed. 
		buf = io.BytesIO()
		buf.write(header)
		return buf

	@asyncio.coroutine
	def commitPacket(self, inputStream):
		""" Commits a packet to the route, to be sent down the wire.
		"""
		inputStream.seek(0)
		inputStream = self.applyFilters(inputStream, self.route.getBuffer())
		yield from self.route.flushBuffer(inputStream)


class GatewayFilterSend(GatewayFilter):
	""" Class for Gateways with a filter element pair on the outgoing message stream. The
	    binary stream will be encoded with the local element and marked for decoding on the
	    remote side with the remote element.
	"""
	def applyFilters(self, inStream, outStream):
		""" Recursively apply the filters in the Gateway chain to the streams. Send
		    filtering requires transcoding from one buffer to another and marking of the stream
		    with the remote element for decoding on the remote end.
		"""
		if isinstance(self.parent, GatewayFilter):
			inStream = self.parent.applyFilters(inStream, io.BytesIO())
		inStream.seek(0)
		outStream.write(headers.HEADER_FILTER_IN)
		filterID = self.route.referenceObject(self.remoteElement)
		ObjectID.serialize(filterID, outStream)
		self.localElement.transcode(inStream, outStream)
		return outStream


class GatewayFilterReply(GatewayFilter):
	""" Class for Gateways with a filter element pair on the reply side of the message stream. The
	    binary stream will be marked with both elements. The remote element will then be applied
	    on the remote end to the response and the return stream will be marked for decoding with
	    the local elelement.
	"""
	def applyFilters(self, inStream, outStream):
		""" Recursively apply the filters in the Gateway chain to the streams. Reply filtering
		    just requires the insertion of the appropriate headers into the message.
		"""
		outStream.write(headers.HEADER_FILTER_OUT)
		remoteID = self.route.referenceObject(self.remoteElement)
		localID = self.route.referenceObject(self.localElement)
		ObjectID.serialize(remoteID, outStream)
		ObjectID.serialize(localID, outStream)
		if isinstance(self.parent, GatewayFilter):
			outStream = self.parent.applyFilters(inStream, outStream)
		else:
			outStream.write(inStream.getvalue())
		return outStream


from route import *
