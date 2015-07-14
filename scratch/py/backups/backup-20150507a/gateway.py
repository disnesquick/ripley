import asyncio
import struct
from util import *
from serialize import *
from errors import *
from shared import *
from transport import TransportClosed
import headers

class Gateway:
	debugMode = False
	def __init__(self, router):
		self.router = router

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
		""" Sets up a server coroutine which will continuously pole the router and handle
		    incoming messages.
		"""
		recvCoro = asyncio.async(self.router.poleTransport(self.handleReceived, self.handleGeneralFailure))
		recvCoro.add_done_callback(lambda fut: fut.result())
		return recvCoro
	##
	# Transcoding functions
	##

	def encode(self, binding, outStream):
		""" Encode an EncodingTypeBinding object into a serialized representation
		    and write this to the outStream supplied.
		"""
		if not isinstance(binding, EncodingTypeBinding):
			raise(TypeError("Expected EncodingTypeBinding not a %s"%(type(binding))))
		for obj, typ in binding:
			typ.encodeStatic(obj, outStream)

	def decode(self, binding):
		""" Decode a DecodingTypeBinding object from the serialized representation
		    and return the encoded objects as a list
		"""
		ret = []
		inStream = binding.data
		for typ in binding.typeTuple:
			ret.append(typ.decodeStatic(inStream))
		return ret 

	def decodeSingle(self, typ, inStream):
		""" Decode a single object from the input stream according to supplied type
		"""
		return typ.decodeStatic(inStream)

	def encodeSingle(self, typ, obj, outStream):
		""" Encode a single object to the output stream according to supplied type
		"""
		typ.encodeStatic(obj, outStream)

	def deserializeArguments(self, iface, byteStream):
		""" This function handles the recovery of objects from a serial data-stream,
		    based on the types of the function parameters. Returns the argument list as
		    an ordered tuple ready to be passed into the function.
		"""
		boundData = DecodingTypeBinding(byteStream, iface.positionalTypes)
		orderedArgs = self.decode(boundData)
		self.dereferenceObjectList(orderedArgs, iface.positionalTypes, iface.argumentIndices)
		return orderedArgs
	
	def deserializeResponse(self, iface, byteStream):
		""" This function handles the recovery of objects from a serial data-stream,
		    based on the types of the function return types. Returns the return list as
		    an ordered tuple ready to be added to the call Future
		"""
		boundData =  DecodingTypeBinding(byteStream, iface.returnTypes)
		responseTuple = self.decode(boundData)
		return self.dereferenceObjectList(responseTuple, iface.returnTypes, iface.returnIndices)

	def bindResponseSerialization(self, iface, orderedArgs):
		""" This function binds the ordered response tuple to the type-list contained
		    in the supplied interface, so that they can be serialized.
		"""
		# Convert return data to a list so that shared objects can be replaced
		# with their ID.
		if not isinstance(orderedArgs, tuple):
			orderedArgs = [orderedArgs]
		else:
			orderedArgs = list(orderedArgs)

		self.referenceObjectList(orderedArgs, iface.returnIndices)
		return EncodingTypeBinding(orderedArgs, iface.returnTypes)

	def bindArgumentSerialization(self, iface, orderedArgs):
		""" This function binds the supplied arguments to the type-list contained in
		    the supplied interface, so that they can be serialized.
		"""
		self.referenceObjectList(orderedArgs, iface.argumentIndices)
		return EncodingTypeBinding(orderedArgs, iface.positionalTypes)

	def referenceObjectList(self, orderedArgs, sharedIndices):
		""" If there are ShareableObjectInterface derived objects in the list, then these
		    should be translated into their shared IDs instead
		"""
		router = self.router
		for idx in sharedIndices:
			orderedArgs[idx] = router.referenceObject(orderedArgs[idx])
		return orderedArgs

	def dereferenceObjectList(self, orderedArgs, orderedTypes, sharedIndices):
		""" Go through the arguments that have been returned from the remote end and
		    translate objects that have a ShareableObjectInterface annotation into either
		    proxies (for objects on the remote side of the gateway), or into the exposed
		    objects (for objects that have previously been shared)
		"""
		router = self.router
		for idx in sharedIndices:
			orderedArgs[idx] = router.dereferenceObject(orderedArgs[idx], orderedTypes[idx], self)
		return orderedArgs

	##
	# Operations for preparing and transmitting a packet
	##

	def beginPacket(self, header):
		""" Returns a valid output buffer to write to. As a root gateway then
		    the buffer will be the final raw buffer provided by the router.
		"""
		buf = self.router.getBuffer()
		buf.write(header)
		return buf

	@asyncio.coroutine
	def commitPacket(self, inputStream):
		""" Commits a packet to the router, to be sent down the wire.
		"""
		yield from self.router.flushBuffer(inputStream)

	##
	# Functions related to transverse object resolution
	##

	@asyncio.coroutine
	def resolveTransverse(self, obj):
		""" Searches the local identity map for the transverse identifier. If it exists
		    then return that shared object ID. If it does not exist then the object
		    is request from the bus and cached in the local identity map before it is
		    returned.
		"""
		ident = obj.__transverse_id__
		try:
			return self.router.getCachedTransverse(ident)
		except KeyError:
			remoteID = (yield from self.transceiveResolve(obj))
			self.router.cacheTransverse(ident, remoteID)
			return remoteID

	##
	# Incoming message routing
	##

	@asyncio.coroutine
	def handleReceived(self, byteStream):
		""" Processes the current waiting packet from byteStream and acts according
		    to the header byte received as the first byte read.
		"""
		header = byteStream.read(1)
		if header == headers.HEADER_HUP:
			raise(TransportClosed())
		elif header == headers.HEADER_RESOLVE:
			yield from self.receiveResolve(byteStream)
		elif header == headers.HEADER_NOTIFY:
			yield from self.receiveNotify(byteStream)
		elif header == headers.HEADER_EVAL:
			yield from self.receiveEval(byteStream)
		elif header == headers.HEADER_REPLY:
			yield from self.receiveReply(byteStream)
		elif header == headers.HEADER_MESSAGE_ERROR:
			yield from self.receiveMessageError(byteStream)
		elif header == headers.HEADER_GENERAL_ERROR:
			yield from self.receiveGeneralError(byteStream)
		elif header == headers.HEADER_FILTER_IN:
			yield from self.modifyIOFilterInput(byteStream)
		elif header == headers.HEADER_FILTER_OUT:
			yield from self.modifyIOFilterOutput(byteStream)
		else:
			raise(DecodingError("Unrecognized header %s"%header))

	@asyncio.coroutine
	def receiveResolve(self, byteStream):
		""" Process a resolution request. A resolution request consists of a message ID
		    and a transverse ID. The transverse ID is mapped to the resident shared
		    object ID if it is present, otherwise an error is sent. 
		"""

		# if stripping the response ID fails then the exception should be sent to the
		# general receiver on the other end.
		responseID = None

		try:
			# Strip out the message ID for response tagging
			responseID = self.decodeSingle(MessageID, byteStream)

			# Strip out the transverse object identifier and resolve it
			transverseID = self.decodeSingle(TransverseID, byteStream)
			sharedID = self.router.resolveTransverseID(transverseID)
			bound = EncodingTypeBinding((sharedID,),(ObjectID,))

			# Send the response down the wire
			yield from self.transmitReply(responseID, bound)
		except Exception as te:
			#This is the only point at which we would not have a valid responseID
			if responseID is None:
				yield from self.handleIncomingGeneralError(te)
			else:
				yield from self.handleIncomingMessageError(responseID, te)

	@asyncio.coroutine
	def receiveNotify(self, byteStream):
		""" Process a notification (An evaluation for which there is no return data).
		    An evaluation request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized arguments
		    for that function call.
		"""
		try:
			#First argument --must-- be a sharedObjectID and local
			callID = self.decodeSingle(ObjectID, byteStream)
			call = self.router.dereferenceObject(callID, ExposedCall)

			# Handle the argument marshalling
			args = self.deserializeArguments(call.iface, byteStream)
	
			# Do the function call
			call.func(*args)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveEval(self, byteStream):
		""" Process a function-evaluation request. An evaluation request consists of a
		    messageID and an objectID (the object must be local and a function/callable),
		    followed by the serialized arguments for that object.
		"""
		# if stripping the response ID fails then the exception should be sent to the
		# general receiver on the other end.
		responseID = None

		try:
			# Strip out the message ID for response tagging
			responseID = self.decodeSingle(MessageID, byteStream)

			#First argument --must-- be a sharedObjectID and local
			callID = self.decodeSingle(ObjectID, byteStream)
			call = self.router.dereferenceObject(callID, ExposedCall)

			# Handle the argument marshalling
			args = self.deserializeArguments(call.iface, byteStream)

			# Do the function call
			returnData = call.func(*args)

			# Finally, bind the returned data and send it as a response
			boundReturn = self.bindResponseSerialization(call.iface, returnData)
			yield from self.transmitReply(responseID, boundReturn)

		except Exception as te:
			#This is the only point at which we would not have a valid responseID
			if responseID is None:
				yield from self.handleIncomingGeneralError(te)
			else:
				yield from self.handleIncomingMessageError(responseID, te)

	@asyncio.coroutine
	def receiveReply(self, byteStream):
		""" Process a response to a function evaluation. A reply notification consists of
		    the message ID of the original message followed by serialized arguments for
		    the response marshalling code.
		"""
		try:
			# Find the response callback and call it on the byteStream
			replyToMessageID = self.decodeSingle(MessageID, byteStream)
			resolve, _ = self.router.resolveMessageID(replyToMessageID)
			resolve(byteStream)
		except Exception as te:
			# Exceptions have to be sent as general exceptions
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveMessageError(self, byteStream):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		"""
		try:
			# Find the error callback
			replyToMessageID = self.decodeSingle(MessageID, byteStream)
			_, error = self.router.resolveMessageID(replyToMessageID)

			#First argument --must-- be a sharedObjectID and a function
			callID = self.decodeSingle(ObjectID, byteStream)
			call = self.router.dereferenceObject(callID, ExposedCall)

			# Handle the argument marshalling
			args = self.deserializeArguments(call.iface, byteStream)

			# Do the function call
			returnData = call.func(*args)

			# Ensure that the function does actually return a valid exception
			if not isinstance(returnData, Exception):
				raise(ObjectIsNotExceptionError(callID))
			
			error(returnData)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def receiveGeneralError(self, byteStream):
		""" An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		"""
		try:
			#First argument --must-- be a sharedObjectID and a function
			callID = self.decodeSingle(ObjectID, byteStream)
			call = self.router.dereferenceObject(callID, ExposedCall)

			# Handle the argument marshalling
			args = self.deserializeArguments(call.iface, byteStream)
	
			# Do the function call
			returnData = call.func(*args)

			# Ensure that the function does actually return a valid exception
			if not isinstance(returnData, Exception):
				raise(ObjectIsNotExceptionError(callID))
			
			self.handleReportedRemoteGeneralError(returnData)

		# Exceptions have to be sent as general exceptions
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def modifyIOFilterInput(self, byteStream):
		""" Remote end-point requests that a filter be applied to the incoming data.
		    This required that the correct filter object be extracted from the local
		    shared object cache and then applied to the stream.
		"""
		try:
			# strip out the incoming filter object
			filterID = self.decodeSingle(ObjectID, byteStream)
			filterElement = self.router.dereferenceObject(filterID, FilterElement)

			# Apply to the stream to generate a new stream
			filteredStream = io.BytesIO()
			filterElement.transcode(byteStream, filteredStream)
			filteredStream.seek(0)

			yield from self.handleReceived(filteredStream)
		except Exception as te:
			yield from self.handleIncomingGeneralError(te)

	@asyncio.coroutine
	def modifyIOFilterOutput(self, byteStream):
		""" Remote end-point requests that a filter be applied to the response to the
		    incoming message. This requires that processing be shifted to a new
		    gateway which has the appropriate filter pair in place.
		"""
		try:
			# strip out the incoming translator pair
			filterID = self.decodeSingle(ObjectID, byteStream)
			filterElementLocal = self.router.dereferenceObject(filterID, FilterElement)
			filterID = self.decodeSingle(ObjectID, byteStream)
			filterElementRemote = self.router.dereferenceObject(filterID, FilterElement, self)
			subGateway = self.sendFilter(filterElementLocal, filterElementRemote)
			yield from subGateway.handleReceived(byteStream)

		except Exception as te:
			yield from self.handleIncomingGeneralError(te)


	##
	# Outgoing message routing
	##

	@asyncio.coroutine
	def transceiveResolve(self, obj):
		""" Takes a transverse descriptor and gets the appropriate shared object ID from
		    the remote end of the connection. Message is sent out as a resolve request
		    followed by a message ID and a transverse ID. Return is expected as a shared
		    object ID.
		"""
		messageID = self.router.generateMessageID()

		outStream = self.beginPacket(headers.HEADER_RESOLVE)
		self.encodeSingle(MessageID, messageID, outStream)
		self.encodeSingle(TransverseID, obj.__transverse_id__, outStream)

		waiter = self.router.waitForReply(messageID, lambda obj : self.decodeSingle(ObjectID, obj))
		yield from self.commitPacket(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitNotify(self, callID, boundArgs):
		""" Sends out a notification to the destination, will not except a response from
		    the other end so no message ID is included.
		"""
		outStream = self.beginPacket(headers.HEADER_NOTIFY)
		self.encodeSingle(ObjectID, callID, outStream)
		self.encode(boundArgs, outStream)

		yield from self.commitPacket(outStream)
	
	@asyncio.coroutine
	def transceiveEval(self, callID, boundArgs, returnDecoder):
		""" transceiveEval is responsible for sending out the EVAL message and then
		    waiting for the response from the server. 
		"""
		outStream = self.beginPacket(headers.HEADER_EVAL)
		messageID = self.router.generateMessageID()

		self.encodeSingle(MessageID, messageID, outStream)
		self.encodeSingle(ObjectID, callID, outStream)
		self.encode(boundArgs, outStream)

		waiter = self.router.waitForReply(messageID, returnDecoder)

		yield from self.commitPacket(outStream)
		return (yield from waiter)

	@asyncio.coroutine
	def transmitReply(self, responseID, boundReply):
		""" transmitReply is responsible for sending out the response to a received message
		    it is only used internally by receiveEval and receiveResolve.
		"""
		outStream = self.beginPacket(headers.HEADER_REPLY)
		self.encodeSingle(MessageID, responseID, outStream)
		self.encode(boundReply, outStream)

		yield from self.commitPacket(outStream)

	@asyncio.coroutine
	def transmitMessageError(self, responseID, errorID, boundArgs):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able to send a transverse error.
		"""
		outStream = self.beginPacket(headers.HEADER_MESSAGE_ERROR)
		self.encodeSingle(MessageID, responseID, outStream)
		self.encodeSingle(ObjectID, errorID, outStream)
		self.encode(boundArgs, outStream)

		yield from self.commitPacket(outStream)

	@asyncio.coroutine
	def transmitGeneralError(self, errorID, boundArgs):
		""" Send a TransverseException object down the wire as an error.
		    This function's called internally and so will only be able to send a transverse error.
		"""
		outStream = self.beginPacket(headers.HEADER_GENERAL_ERROR)
		self.encodeSingle(ObjectID, errorID, outStream)
		self.encode(boundArgs, outStream)

		yield from self.commitPacket(outStream)

	##
	# Error handling functions
	##

	def handleGeneralFailure(self, error):
		""" If everything else fails then call this function as a final resort
		    Its job is to clean up the connection (i.e. cleanly disengage from the
		    bus and then report a complete and final failure to the outer code.
		"""
		asyncio.get_event_loop().call_soon(self.router.close)
		raise(error)

	def handleFatalRemoteFailure(self, error):
		""" When the remote end is not able to support error handlin, there is no way
		    to recover, the local end needs to gracefully disconnect or ignore that
		    remote peer.
		"""
		yield from self.close()
		raise(RemoteEndFailure(error, self.router))
	
	def handleIncomingMessageError(self, messageID, error):
		""" Handler for the situation when an incoming message (an eval or resolve) has
		    triggered an error, such that the error in question should be send as an error
		    reply as a response to the message.
		"""
		if not isinstance(error, TransverseException):
			if Gateway.debugMode:
				# In debug mode give a stringified version of the error back to the client
				raise(error)
				serialError = SerializedError(repr(error))
				yield from self.handleIncomingMessageError(messageID, serialError)
			else:
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				yield from self.handleIncomingMessageError(messageID, UnknownError())
		else:
			try:
				transverse = error.__iface_members__["__constructor__"]
				errorID = (yield from self.resolveTransverse(transverse))
				yield from self.transmitMessageError(messageID, errorID, error.getBoundArgs(self))
			except Exception as err:
				yield from self.handleFatalRemoteFailure(err)
	
	def handleIncomingGeneralError(self, error):
		""" Handler for the situation when when an incoming notification (notify, reply, error)
		    has triggered an error and there is therefore no specific message to append the
		    error-response to so it should just be reported as a general error.
		"""
		if not isinstance(error, TransverseException):
			if Gateway.debugMode:
				# In debug mode give a stringified version of the error back to the client
				raise(error)
				serialError = SerializedError(repr(error))
				yield from self.handleIncomingGeneralError(serialError)
			else:
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				yield from self.handleIncomingGeneralError(UnknownError())
		else:
			try:
				transverse = error.__iface_members__["__constructor__"]
				errorID = (yield from self.resolveTransverse(transverse))
				yield from self.transmitGeneralError(errorID, error.getBoundArgs(self))
			except Exception as err:
				yield from self.handleFatalRemoteFailure(err)

	def handleReportedRemoteGeneralError(self, error):
		""" Local side of handleIncomingGeneralError: The remote side reports that the local side
		    has caused an error non-specific to any IDed message.
		"""
		raise(error)


class GatewayFilter(Gateway):
	""" Base class for Gateways with a filter element pair active on it, used for testing
	    whether to apply filters or not.
	"""
	def __init__(self, parent, localElement, remoteElement):
		super().__init__(parent.router)
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
		""" Commits a packet to the router, to be sent down the wire.
		"""
		inputStream.seek(0)
		inputStream = self.applyFilters(inputStream, self.router.getBuffer())
		yield from self.router.flushBuffer(inputStream)


class GatewayFilterSend(GatewayFilter):
	""" Class for Gateways with a filter element pair on the outgoing message stream. The
	    binary stream will be encoded with the local element and marked for decoding on the
	    remote side with the remote element.
	"""
	def applyFilters(self, inputStream, outputStream):
		""" Recursively apply the filters in the Gateway chain to the streams. Send
		    filtering requires transcoding from one buffer to another and marking of the stream
		    with the remote element for decoding on the remote end.
		"""
		if isinstance(self.parent, GatewayFilter):
			inputStream = self.parent.applyFilters(inputStream, io.BytesIO())
		inputStream.seek(0)
		outputStream.write(headers.HEADER_FILTER_IN)
		filterID = self.router.referenceObject(self.remoteElement)
		self.encodeSingle(ObjectID, filterID, outputStream)
		self.localElement.transcode(inputStream, outputStream)
		return outputStream


class GatewayFilterReply(GatewayFilter):
	""" Class for Gateways with a filter element pair on the reply side of the message stream. The
	    binary stream will be marked with both elements. The remote element will then be applied
	    on the remote end to the response and the return stream will be marked for decoding with
	    the local elelement.
	"""
	def applyFilters(self, inputStream, outputStream):
		""" Recursively apply the filters in the Gateway chain to the streams. Reply filtering
		    just requires the insertion of the appropriate headers into the message.
		"""
		outputStream.write(headers.HEADER_FILTER_OUT)
		remoteID = self.router.referenceObject(self.remoteElement)
		localID = self.router.referenceObject(self.localElement)
		self.encodeSingle(ObjectID, remoteID, outputStream)
		self.encodeSingle(ObjectID, localID, outputStream)
		if isinstance(self.parent, GatewayFilter):
			outputStream = self.parent.applyFilters(inputStream, outputStream)
		else:
			outputStream.write(inputStream.getvalue())
		return outputStream


from router import *
