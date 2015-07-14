### @declare transport_gateway
  #
  # @require util
  # @require serialize
  # @require shared
  # @require error
###

class ExposedCall
	constructor : (func, iface) ->
		@func = func
		@iface = iface

	
class TransportGateway
	HEADER_HUP           : "\x00"
	HEADER_RESOLVE       : "\x11"
	HEADER_NOTIFY        : "\x12"
	HEADER_EVAL          : "\x13"
	HEADER_REPLY         : "\x14"
	HEADER_MESSAGE_ERROR : "\x15"
	HEADER_GENERAL_ERROR : "\x16"
	HEADER_TIME          : "\x17"

	constructor : (transcoder, transport, debugMode = false) ->
		@transcoder = transcoder
		@transport = transport
		@debugMode = debugMode
		@remoteTransverseMap = {}
		@exposedTransverseMap = {}
		@responseWaitingQueue = {}
		@exposedObjects = {}
		@isOpen = false
		@sharedCount = 0
		@messageCount = 0
		self = @
		transport.setCallbacks((message) ->
			self.processReceived(message)
		,(error) ->
			alert(error))

	classFactoryFactory : (cls) ->
		### Little helper function that returns a new object without having to do that
		    whole "new" shit because that don't fly in procedure-only call creation
		    convention. I much prefer the python way of doing this shizzle.
		###
		empty = () ->
		empty.prototype = cls.prototype
		(args...) ->
			obj = new empty
			cls.apply(obj, args)
			obj

	close : () ->
		### Closes the transport poling loop by setting the exit flag and causing the transport
		    to unblock and return a NULL action.
		###
		@isOpen = false
		@transport.hangUp()

	generateMessageID : () ->
		### Generates a message ID in the form of a byte-string. 
		    Message IDs are based on a simple incrementation counter.
		    TODO: when a sufficient buffer length has passed, reset the message ID counter.
		###
		@messageCount += 1
		SerialID.integersToBytes(@messageCount)

	generateShareID : () ->
		### Generates an object ID in the form of a byte-string. Object IDs consist of the gateway tag plus
		    a unique code for the object itself. This allows objects to be mapped to a particular
		    end-point of the gateway.
		    TODO: when a sufficient buffer length has passed, reset the message ID counter.
		###
		@sharedCount += 1
		SerialID.integersToBytes(@destID, @sharedCount)

	shareObject : (obj) ->
		### Marks an object as a shared object and stores it in the shared object
		    list for retrieval through an object reference.
		###
		obj.__shared_id__ = shareID = @generateShareID()
		@exposedObjects[shareID] = obj
		shareID

	exposeObjectImplementation : (cls) ->
		### Exposes an object that has been marked as an implementation of an object
		    to the other side(s) of the transport. If the interface is marked as
		    non-constructable, then no constructor method will be made available.
		###
		iface = cls::__implementation_of__
		for name, member of iface.__iface_members__ when name != "__constructor__"
			uuid = member.__transverse_id__
			@exposedTransverseMap[uuid] = @shareObject(new ExposedCall(cls::[name], member))

		if "__constructor__" of iface.__iface_members__
			member = iface.__iface_members__["__constructor__"]
			uuid = member.__transverse_id__
			@exposedTransverseMap[uuid] = @shareObject(new ExposedCall(@classFactoryFactory(cls), member))

	decodeExposed : (argList, typeList) ->
		### Go through the arguments that have been returned from the remote end and translate
		    objects that have a ShareableObjectInterface annotation into either proxies (for
		    objects on the remote side of the gateway), or into the exposed objects (for objects
		    that have previously been shared)
		###
		for arg,idx in argList
			typ = typeList[idx]
			if typ instanceof ShareableObjectInterface
				# TODO check that the objects belongs to this gateway but is invalid TODO
				# TODO (since the object will be annotated with the belonging)       TODO
				if arg of @exposedObjects
					arg = @exposedObjects[arg]
					if not typ.implementedBy arg
						throw new Error("#{ arg.constructor.name } was not of type #{ typ.objName } as specified in the interface")
				else
					arg = new (typ.getProxyClass())(@, arg)
				argList[idx] = arg
		argList
	
	encodeExposed : (argList, typeList) ->
		### If there are ShareableObjectInterface derived objects in the list, then these
		    should be translated into their shared IDs instead
		###
		for arg, idx in argList
			typ = typeList[idx]
			if typ instanceof ShareableObjectInterface
				argList[idx] = if arg.__shared_id__? then arg.__shared_id__ else @shareObject(arg)
		argList

	runCall : (bound) ->
		bound.doCallOn(this)

	##
	# 
	# Receiving code for transport gateway
	#
	##

	processReceived : (charStream) ->
		### Main callback for receiving data from the transport. Takes a data-stream
		    and a transport proxy for sending replies to
		###
		remoteEndHandle = @
		header = charStream.read(1)
		switch header
			when @HEADER_HUP
				@hangUp()
			when @HEADER_RESOLVE
				@receiveResolve(charStream, remoteEndHandle)
			when @HEADER_NOTIFY
				@receiveNotify(charStream, remoteEndHandle)
			when @HEADER_EVAL
				@receiveEval(charStream, remoteEndHandle)
			when @HEADER_REPLY
				@receiveReply(charStream, remoteEndHandle)
			when @HEADER_MESSAGE_ERROR
				@receiveMessageError(charStream, remoteEndHandle)
			when @HEADER_GENERAL_ERROR
				@receiveGeneralError(charStream, remoteEndHandle)
			else
				throw new DecodingError

	receiveResolve : (charStream, remoteEndHandle) ->
		### Process a resolution request. A resolution request consists of a message ID
		    and a transverse ID. The transverse ID is mapped to the resident shared
		    object ID if it is present, otherwise an error is sent. 
		###
		try
			# Strip out the message ID for response tagging
			responseID = @transcoder.decodeSingle(MessageID, charStream)

			# Strip out the transverse object identifier
			transverseID = @transcoder.decodeSingle(TransverseID, charStream)

			if not (transverseID of @exposedTransverseMap)
				# This gateway does not know about this transverse identifier
				throw new UnknownTransverseIDError(transverseID)
			else
				# return the exposed object associated with the transverse identifier
				sharedID = @exposedTransverseMap[transverseID]
				remoteEndHandle.transmitReply(responseID, new EncodingTypeBinding([sharedID], [ObjectID]))
		catch err
			@handleIncomingMessageError(responseID, err, remoteEndHandle)

	receiveNotify : (charStream, remoteEndHandle) ->
		### Process a notification (An evaluation for which there is no return data).
		    An evaluation request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized arguments
		    for that function call.
		###
		try
			#First argument --must-- be a sharedObjectID
			callID = @transcoder.decodeSingle(ObjectID, charStream)
			if not callID in @exposedObjects
				throw new UnknownObjectIDError(callID)
			else
				call = @exposedObjects[callID]

			# Handle the argument marshalling
			boundData = call.iface.argDecodeBinder(byteStream)
			args = self.transcoder.decode(boundData)
			args = self.decodeExposed(args, boundData.typeTuple)

			# The first argument is ALWAYS a 'this' reference
			[self,args] = [args[0],args[1..]]

			# Do the function call
			call.func.apply(self, args)

		# Exceptions have to be sent as general exceptions
		catch err
			@handleIncomingGeneralError(err, remoteEndHandle)

	receiveEval : (charStream, remoteEndHandle) ->
		### Process a function-evaluation request. An evaluation request consists of a
		    message ID and an object ID (the object must be local and a function/callable),
		    followed by the serialized arguments for that object.
		###
		# if stripping the response ID fails then the exception should be sent to the general
		# receiver on the other end.
		responseID = null
		try
			# Strip out the message ID for response tagging
			responseID = @transcoder.decodeSingle(MessageID, charStream)

			#First argument --must-- be a sharedObjectID
			callID = @transcoder.decodeSingle(ObjectID, charStream)
			if not callID in @exposedObjects
				throw new UnknownObjectIDError(callID)
			else
				call = @exposedObjects[callID]
		
			# Handle the argument marshalling
			boundData = call.iface.argDecodeBinder(charStream)
			args = @transcoder.decode(boundData)
			args = @decodeExposed(args, boundData.typeTuple)
	
			
			# The first argument is ALWAYS a 'this' reference
			[self,args] = [args[0],args[1..]]

			# Do the function call
			returnData = call.func.apply(self, args)

			# Convert return data to a list so that shared objects can be replaced
			# with their ID.
			if not (returnData instanceof Array)
				returnData = [returnData]
			returnData = @encodeExposed(returnData, call.iface.returnTypes)
			
			# Finally, bind the returned data and send it as a response
			boundReturn = call.iface.retEncodeBinder(returnData)
			remoteEndHandle.transmitReply(responseID, boundReturn)

		catch err
			if responseID is null
				@handleIncomingGeneralError(err, remoteEndHandle)
			else
				@handleIncomingMessageError(responseID, err, remoteEndHandle)

	receiveReply : (charStream, remoteEndHandle) ->
		### Process a response to a function evaluation. A reply notification consists of
		    the message ID of the original message followed by serialized arguments for
		    the response marshalling code.
		###
		try
			# Strip out the message ID for response tagging
			replyToMessageID = @transcoder.decodeSingle(MessageID, charStream)

			# Ensure that the message is a response to a message from this gateway
			if not (replyToMessageID of @responseWaitingQueue)
				# send a general error to the other-side if this message was unknown
				throw new UnknownMessageIDError(replyToMessageID)

			# Grab the future and return argument binder
			resolve = @responseWaitingQueue[replyToMessageID][0]
			delete @responseWaitingQueue[replyToMessageID]

			resolve(charStream)

		# Exceptions have to be sent as general exceptions
		catch err
			@handleIncomingGeneralError(err, remoteEndHandle)

	receiveMessageError : (charStream, remoteEndHandle) ->
		### An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		###
		try
			# Strip out the message ID for response tagging
			replyToMessageID = @transcoder.decodeSingle(MessageID, byteStream)
        	
			# Ensure that the message is a response to a message from this gateway
			if not (replyToMessageID of @responseWaitingQueue)
				# send a general error to the other-side if this message was unknown
				throw new UnknownMessageIDError(replyToMessageID)

			# Grab the future but discard the return binder
			error = @responseWaitingQueue[replyToMessageID][1]
			delete @responseWaitingQueue[replyToMessageID]

			# First argument --must-- be a sharedObjectID and a function
			callID = @transcoder.decodeSingle(ObjectID, charStream)
			if not (callID of @exposedObjects)
				throw new UnknownObjectIDError(callID)
			else
				call = @exposedObjects[callID]

			# Handle the argument marshalling
			boundData = call.iface.argDecodeBinder(charStream)
			args = @transcoder.decode(boundData)
			args = @decodeExposed(args, boundData.typeTuple)
	
			# The first argument is ALWAYS a 'this' reference
			[self,args] = [args[0],args[1..]]

			# Do the function call
			returnData = call.func.apply(self, args)

			# Ensure that the function does actually return a valid exception
			if not (returnData instanceof Error)
				throw new ObjectIsNotExceptionError(callID)
			
			error(returnData)

		# Exceptions have to be sent as general exceptions
		catch err
			@handleIncomingGeneralError(err, remoteEndHandle)
	
	receiveGeneralError : (charStream, remoteEndHandle) ->
		### An error is a hybrid of a reply and a notification. It consists of the message
		    ID of the original message followed by an object ID for the error function to
		    call.
		###
		try
			# First argument --must-- be a sharedObjectID and a function
			callID = @transcoder.decodeSingle(ObjectID, charStream)
			if not (callID of @exposedObjects)
				throw new UnknownObjectIDError(callID)
			else
				call = @exposedObjects[callID]

			# Handle the argument marshalling
			boundData = call.iface.argDecodeBinder(charStream)
			args = @transcoder.decode(boundData)
			args = @decodeExposed(args, boundData.typeTuple)
	
			# The first argument is ALWAYS a 'this' reference
			[self,args] = [args[0],args[1..]]

			# Do the function call
			returnData = call.func.apply(self, args)

			# Ensure that the function does actually return a valid exception
			if not (returnData instanceof Error)
				throw new ObjectIsNotExceptionError(callID)
			
			@handleReportedRemoteGeneralError(returnData, remoteEndHandle)

		# Exceptions have to be sent as general exceptions
		catch err
			@handleIncomingGeneralError(err, remoteEndHandle)
	
	##
	# 
	# Sending code for transport gateway
	#
	##

	transceiveResolve : (obj) ->
		### Takes a transverse descriptor and gets the appropriate shared object ID from the remote
		    end of the connection. Message is sent out as a resolve request followed by a message ID
		    and a transverse ID. Return is expected as a shared object ID.
		###
		outStream = @transport.beginWrite()
		messageID = @generateMessageID()
		
		outStream.write(@HEADER_RESOLVE)
		@transcoder.encodeSingle(MessageID, messageID, outStream)
		@transcoder.encodeSingle(TransverseID, obj.__transverse_id__, outStream)

		waiter = @waitOnReply(messageID, (data) -> new DecodingTypeBinding(data, [ObjectID]))
		@transport.send(outStream)

		return waiter

	transmitNotify : (callID, args) ->
		### Sends out a notification to the destination, will not except a response from the other
		    end so no message ID is included.
		###
		outStream = @transport.beginWrite()
		
		outStream.write(@HEADER_NOTIFY)
		@transcoder.encodeSingle(ObjectID, callID, outStream)
		@transcoder.encode(args, outStream)

		@transport.send(outStream)

	transceiveEval : (callID, args, returnBinder) ->
		### transceiveEval is responsible for sending out the EVAL message and then waiting
		    for the response from the server. 
		###
		outStream = @transport.beginWrite()
		messageID = @generateMessageID()
		
		outStream.write(@HEADER_EVAL)
		@transcoder.encodeSingle(MessageID, messageID, outStream)
		@transcoder.encodeSingle(ObjectID, callID, outStream)
		@transcoder.encode(args, outStream)
		
		waiter = @waitOnReply(messageID,returnBinder)
		@transport.send(outStream)

		return waiter

	transmitReply : (responseID, obj) ->
		### transmitReply is responsible for sending out the response to a received message
		    it is only used internally by receiveEval and receiveResolve.
		###
		outStream = @transport.beginWrite()
		
		outStream.write(@HEADER_REPLY)
		@transcoder.encodeSingle(MessageID, responseID, outStream)
		@transcoder.encode(obj, outStream)

		@transport.send(outStream)

	transmitMessageError : (responseID, errorID, args) ->
		### Send a TransverseException object down the wire as an error.
		    This function is called internally and so will only be able to send a transverse error.
		###
		outStream = @transport.beginWrite()
		
		outStream.write(@HEADER_MESSAGE_ERROR)
		@transcoder.encodeSingle(MessageID, responseID, outStream)
		@transcoder.encodeSingle(ObjectID, errorID, outStream)
		@transcoder.encode(args, outStream)

		@transport.send(outStream)

	transmitGeneralError : (errorID, args) ->
		### Send a TransverseException object down the wire as an error.
		    This function is called internally and so will only be able to send a transverse error.
		###
		outStream = @transport.beginWrite()
		
		outStream.write(@HEADER_GENERAL_ERROR)
		@transcoder.encodeSingle(ObjectID, errorID, outStream)
		@transcoder.encode(args, outStream)

		@transport.send(outStream)
		
	##
	# 
	# General auxilliary functions for transmitting/transceiving
	#
	##

	waitOnReply : (messageID, binder) ->
		### Sets up a future which will be activated when the response to the outgoing message
		    comes in.
		###
		self = this
		new Promise (resolve, reject) ->
			self.responseWaitingQueue[messageID] = [resolve,reject]
		.then (charStream) ->
			# Handle the argument marshalling
			boundData = binder(charStream)
			response = self.transcoder.decode(boundData)
			response = self.decodeExposed(response, boundData.typeTuple)

			# Decode single items from list wrapper
			if response.length == 1
				response = response[0]
			response

	resolveTransverse : (obj) ->
		### Searches the local identity map for the transverse identifier. If it exists
		    then return that shared object ID. If it does not exist then the object
		    is request from the bus and cached in the local identity map before it is
		    returned.
		###
		ident = obj.__transverse_id__
		self = this
		if not (ident of @remoteTransverseMap)
			self.transceiveResolve(obj)
			.then (msg) ->
				self.remoteTransverseMap[ident] = msg
				msg
		else
			#TODO this is a pretty inefficient way of doing this TODO
			new Promise (resolve, error) ->
				resolve(self.remoteTransverseMap[ident])

	##
	#
	# Default error handling
	#
	##

	handleGeneralFailure : (error) ->
		### If everything else fails then call this function as a final resort
		    Its job is to clean up the connection (i.e. cleanly disengage from the
		    bus and then report a complete and final failure to the outer code.
		###
		@close()
		throw error

	handleFatalRemoteFailure : (error, remoteEndHandle) ->
		### When shit is so fucked up on the remote end that there is no way
		    to recover, the local end needs to gracefully disconnect or ignore that
		    remote peer.
		###
		@close()
		throw new RemoteEndFailure(error, remoteEndHandle)

	handleIncomingMessageError : (messageID, error, remoteEndHandle) ->
		### Handler for the situation when an incoming message (an eval or resolve) has
		    triggered an error, such that the error in question should be send as an error
		    reply as a response to the message.
		###
		if not (error instanceof TransverseException)
			# If the error is not a 'natural' Transverse error then it must be encoded as one to send
			if @debugMode
				# In debug mode give a stringified version of the error back to the client
				@handleIncomingMessageError(messageID, new SerializedError(error.toString(),error.stack), remoteEndHandle)

			else
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				@handleIncomingMessageError(messageID, new UnknownError(), remoteEndHandle)
		else
			try
				@resolveTransverse(error.__implementation_of__.__iface_members__["__constructor__"])
				.then (errorID) ->
					remoteEndHandle.transmitMessageError(messageID, errorID, error.getBoundArgs())
			catch err
				@handleFatalRemoteFailure(err, remoteEndHandle)
	
	handleIncomingGeneralError : (error, remoteEndHandle) ->
		### Handler for the situation when when an incoming notification (notify, reply, error)
		    has triggered an error and there is therefore no specific message to append the
		    error-response to so it should just be reported as a general error.
		###
		if not (error instanceof TransverseException)
			# If the error is not a 'natural' Transverse error then it must be encoded as one to send
			if @debugMode
				# In debug mode give a stringified version of the error back to the client
				@handleIncomingGeneralError(messageID, new SerializedError(error.toString(),error.stack), remoteEndHandle)

			else
				# any unhandled exceptions will have to be passed down the line
				# as an unknown error to avoid giving state information about the server
				@handleIncomingGeneralError(messageID, new UnknownError(), remoteEndHandle)
		else
			try
				@resolveTransverse(error.__implementation_of__.__iface_members__["__constructor__"])
				.then (errorID) ->
					remoteEndHandle.transmitGeneralError(errorID, error.getBoundArgs())
			catch err
				@handleFatalRemoteFailure(err, remoteEndHandle)

	handleReportedRemoteGeneralError : (error, remoteEndHandle) ->
		### Local side of handleIncomingGeneralError: The remote side reports that the local side
		    has caused an error non-specific to any IDed message.
		###
		throw error
