### @declare connection
  #
  # @require headers
###
class Connection
	constructor : (bus, connectionID) ->
		# Object brokering
		@objectToObjectID = {}
		@objectIDToObject = {}
		@sharedCount = -1
		@services = []
		@proxyTokens = {}
		
		# Connection to bus
		@bus = bus
		@connectionID = connectionID
		
		# Transverse caching
		@cachedTransverse = {}
	
	##
	# Code for handling object caching
	##
	
	generateObjectID : () ->
		### Generates an object ID in the form of a SerialID.
		
		    Referencess are transfered in the form of a connection-specific
		    unique identifier plus an identifier for the connection itself.
		    However, this connectionID is handled elsewhere.
		###
		@objectCount += 1
		SerialID.integerToBytes(@objectCount)
	
	objectToReference : (obj) ->
		### Obtains a reference identifier for an object.
		
		    If the object has been shared previously then the previous reference
		    is returned, otherwise a reference is generated and marked against
		    the object.  The connection ID is added for local objects to create
		    a complete reference.
		###
		if (obj isinstance ProxyObject)
			obj.reference
		else if (obj of @objectToObjectID)
			objectID = @objectToObjectID[obj]
			[@connectionID, objectID]
		else
			# This is a new object so generate the reference and store them
			objectID = @generateObjectID()
			@objectIDToObject[objectID] = obj
			@objectToObjectID[obj] = objectID
			[@connectionID, objectID]
	
	referenceToObject : (reference, typ) ->
		### Maps an incoming object reference to a python object.
		
		    Local objects will be mapped to their local python object whereas
		    remote objects will be wrapped in an object proxy.
		###
		[connectionID, objectID] = reference
		
		if (connectionID == @connectionID)
			if not (objectID of @objectIDToObject)
				throw new UnknownObjectIDError(objectID)
			obj = @objectIDToObject[objectID]
			if not (obj isinstance typ)
				throw new ReferenceTypeMismatchError(obj, typ)
		else
			try
				destination = @proxyTokens[connectionID]
			catch err
				throw new RouteNotFound(@connectionID, connectionID,
				                        reference, typ)
			obj = new (typ.getProxyClass())(destination, reference)
		obj
	
	##
	# Transcoding functions
	##
	
	serializeObjects : (objs, objTypes, outStream) ->
		### Serializes a list of objects.
		
		    The list of objects `objs' is serialized according to the types in
		    the congruent list objTypes and written directly to outStream in
		    binary form.
		###
		for obj, idx in objs
			@serializeObject(obj, typ[idx], outStream)
		return # Null
	
	serializeObject : (obj, typ, outStream) ->
		### Serializes a single object.
		
		    The object `obj' is serialized according to the type `typ' and
		    written to outStream in binary form. Objects can be PassByValue
		    types, which will be directly serialized, or they can be local
		    objects, in which case they will be assigned a suitable reference
		    and that will be serialized.
		###
		if (typ isinstance PassByValue)
			if (typ isinstance ComplexPassByValue)
				typ.serialize(obj, this, outStream)
			else
				typ.serialize(obj, outStream)
		else
			ref = @objectToReference(obj)
			Reference.serialize(ref, outStream)
		return # Null
	
	deserializeObjects : (objTypes, inStream) ->
		### Deserializes a list of objects.
		
		    A list of objects is extracted from the binary inStream according
		    to the list of types `objTypes'.
		###
		(@deserializeObject(typ, inStream) for typ in objTypes)
	
	deserializeObject : (typ, inStream) ->
		### Deserializes a single object from inStream.
		
		    According to the type typ, PassByValue objects are directly
		    deserialized as they are serialized. For other kinds of objects a
		    reference is deserialized and this is used to retrieve the object or
		    create the appropriate proxy.
		###
		if (typ isinstance PassByValue)
			if (typ isinstance ComplexPassByValue)
				typ.deserialize(this, inStream)
			else
				typ.deserialize(inStream)
		else
			ref = Reference.deserialize(inStream)
			@referenceToObject(ref, typ)
	
	##
	# Function related to transverse object resolution
	##
	
	addTransverseMap : (transverseMap) ->
		### Adds a dictionary of transverse mappings to the Connection.
		
		    This method is usually applied when a ServiceImplementatiob object
		    is offered on a Connection. The list of TransverseID -> Object
		    mappings is added to this Connection so that future transverse
		    resolutions will return the objects in question (or rather, the
		    references to them).
		###
		@transverseMaps.append(transverseMap)
		return # Null
	
	transverseIDToReference : (transverseID) ->
		### Maps a TransverseID to a Reference to the appropriate object.
		
		    Looks through the handled transvese maps to find the object
		    corresponding to the TransverseID supplied and then maps the object
		    to a Reference, for transmission over the wire.
		###
		for transverseMap of @transverseMaps
			if transverseID of transverseMap
				obj = transverseMap[transverseID]
				return @objectToReference(obj)
		throw new UnknownTransverseIDError(transverseID)
	
	##
	# Incoming message routing
	##
	
	handleReceived : (origin, inStream) ->
		### Processes the current waiting packet from inStream.
		
		    This procedure retrieves a message packet from inStream and acts
		    according to the header byte received (the first byte read) to pass
		    further processing to the appropriate subprocedure.
		###
		header = inStream.read(1)
		if header == headers.HEADER_RESOLVE
			@receiveResolve(origin, inStream)
		else if header == headers.HEADER_NOTIFY
			@receiveNotify(origin, inStream)
		else if header == headers.HEADER_EVAL
			@receiveEval(origin, inStream)
		else if header == headers.HEADER_REPLY
			@receiveReply(origin, inStream)
		else if header == headers.HEADER_MESSAGE_ERROR
			@receiveMessageError(origin, inStream)
		else if header == headers.HEADER_GENERAL_ERROR
			@receiveGeneralError(origin, inStream)
		else if header == headers.HEADER_FILTER_IN
			@modifyIOFilterInput(origin, inStream)
		else if header == headers.HEADER_FILTER_OUT
			@modifyIOFilterOutput(origin, inStream)
		else
			throw new DecodingError("Unrecognized header %s"%header)
		return # Null
	
	receiveResolve : (origin, inStream) ->
		### Process a resolution request.
		
		    A resolution request consists of a message ID and a transverse ID.
		    The transverse ID is mapped to the resident shared object ID if it
		    is present, otherwise an error is sent. 
		###
		# Strip out the message ID for response tagging
		messageID = MessageID.deserialize(inStream)
		
		try
			# Strip out the transverse object identifier and resolve it
			transverseID = TransverseID.deserialize(inStream)
			reference = @transverseIDToReference(transverseID)
			
			# Create the response object
			outStream = origin.getOutputBuffer()
			outStream.write(headers.HEADER_REPLY)
			MessageID.serialize(messageID, outStream)
			Reference.serialize(reference, outStream)
			
			# Transmit the response
			outStream.commit()
		
		catch te
			@handleIncomingMessageError(origin, messageID, te)
		return # Null
	
	receiveNotify : (origin, inStream) ->
		### Process a notification.
		
		    A notification is an  evaluation for which there is no return data.
		    The request consists of a message ID and an object ID (the object
		    must be local and a function/callable), followed by the serialized
		    arguments for that function call.
		###
		#First argument --must-- be a sharedObjectID and local
		call = @deserializeObject(ExposedCallable, inStream)
		
		# Make the call
		call.handleNotification(this, inStream)
		return # Null
	
	receiveEval : (origin, inStream) ->
		### Process an evaluation request.
		
		    An evaluation request consists of a messageID and an objectID (the
		    object must be local and a function/callable), followed by the
		    serialized arguments for that object.
		###
		# Strip out the message ID for response tagging
		messageID = MessageID.deserialize(inStream)
		
		try
			#First argument --must-- be an ExposedCallable object
			call = @deserializeObject(ExposedCallable, inStream)
			
			# Create the response object
			outStream = origin.getOutputBuffer()
			outStream.write(headers.HEADER_REPLY)
			MessageID.serialize(messageID, outStream)
			
			# Make the call			
			call.handleEval(this, inStream, outStream)
			
			# Send the message
			outStream.commit()
		
		catch te
			@handleIncomingMessageError(origin, messageID, te)
		return # Null
	
	receiveReply : (origin, inStream) ->
		### Process a response to an evaluation or resolution request.
		
		    A reply notification consists of the message ID of the original
		    message followed by serialized arguments for the response
		    marshalling code.
		###
		# Find the response callback and call it on the inStream
		messageID = MessageID.deserialize(inStream)
		[doneCall, _] = @bus.resolveMessageID(messageID, origin.lastRoute)
		doneCall(inStream)
		return # Null
	
	def receiveMessageError : (origin, inStream) ->
		### Process an error response to a function evaluation.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    the message ID of the original message followed by an object ID for
		    the exception object.
		###
		# Find the error callback
		messageID = MessageID.deserialize(inStream)
		[_, error] = self.bus.resolveMessageID(messageID, origin.lastRoute)
		
		transverseID = TransverseID.deserialize(inStream)
		try
			obj = @transverseIDToObject(transverseID)
			exceptionObject = obj.handleFetch(this, inStream)
			error(exceptionObject)
		catch
			error(new ErrorUnsupported(transverseID))
	
	receiveGeneralError : (origin, inStream) ->
		### Process an error received as a general failure.
		
		    An error is a hybrid of a reply and a notification. It consists of
		    an object ID for the error function to call.
		###
		transverseID = TransverseID.deserialize(inStream)
		try
			obj = @transverseIDToObject(transverseID)
			exceptionObject = obj.handleFetch(this, inStream)
			error(exceptionObject)
		catch
			error(new ErrorUnsupported(transverseID))
		@bus.handleGeneralError(origin, exceptionObject)
	
	modifyIOFilterInput : (origin, inStream) ->
		### Process the application of a filter to the incoming stream.
		
		    Remote end-point requests that a filter be applied to the incoming
		    data.  This required that the correct filter object be extracted
		    from the local shared object cache and then applied to the stream.
		###
		# strip out the incoming filter object (must be local)
		filterElement = @deserializeObject(FilterElement, inStream)
		
		# Apply to the stream to generate a new stream
		filteredStream = new StringIO()
		filterElement.transcode(inStream, filteredStream)
		filteredStream.seek(0)
		
		@handleReceived(origin, filteredStream)
		return # Null
	
	modifyIOFilterOutput : (origin, inStream) ->
		### Process the addition of a filter on the response path.
		
		    Remote end-point requests that a filter be applied to the response
		    to the incoming message. This requires that processing be shifted to
		    a new gateway which has the appropriate filter pair in place.
		###
		# strip out the incoming translator pair
		filterElementLocal = @deserializeObject(FilterElement, inStream)
		filterElementRemoteRef = Reference.deserialize(inStream)
		subOrigin = FilteredResponseRoute(origin, filterElementLocal,
		                                  filterElementRemoteRef)
		@handleReceived(subOrigin, inStream)
		return # Null
	
	##
	# Outgoing message routing
	##
	
	transceiveResolve : (destination, transverseID) ->
		### Request the remote object ID corresponding to a transverse ID.
		
		    Takes a transverse descriptor and gets the appropriate shared
		    object ID from the remote end of the connection. Message is sent out
		    as a resolve request followed by a message ID and a transverse ID.
		    Return is expected as a shared object ID.
		###
		new Promise((result, error) ->
			# First, try and retrieve the result from the local cache.
			cacheID = [destination.transport.remoteBusID, transverseID]
			if cacheID of @cachedTransverse
				result(@cachedTransverse[cacheID])
			# Unknown: Resolve from the remote end of the Route.
			else
				# Create the response listener for the remote resolution.
				reply = (inStream) ->
					try
						resolved = Reference.deserialize(inStream)
						@cachedTransverse[cacheID] = resolved
						result(resolved)
					catch e
						error(e)
				
				messageID = @bus.waitForReply(reply, fut.setError,
				                              destination.lastRoute)
				
				# Format the outgoing message to the wire
				outStream = destination.getOutputBuffer()
				outStream.write(headers.HEADER_RESOLVE)
				MessageID.serialize(messageID, outStream)
				TransverseID.serialize(transverseID, outStream)
				outStream.commit()
		)
	
	transmitNotify : (destination, callID) ->
		### Call a remote function without any response.
		
		    This function prepares an output stream connected to the destination
		    Route provided. The message type will be tagged as a notification so
		    no reply is expected.
		###
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_NOTIFY)
		Reference.serialize(callID, outStream)
		outStream
	
	transceiveEval : (destination, callID) ->
		### Call a remote function and retrieve the reply.
		
		    transceiveEval is responsible for sending out the EVAL message and
		    then waiting for the response from the server. 
		###
		outStream = destination.getOutputBuffer()
		fut = new Promise((result, error) ->
			messageID = @bus.waitForReply(result, error, destination.lastRoute)
			
			# Format the outgoing message to the wire
			outStream.write(headers.HEADER_EVAL)
			MessageID.serialize(messageID, outStream)
			Reference.serialize(callID, outStream)
		)
		[outStream, fut]
	
	transmitMessageError : (destination, messageID, error) ->
		### Transmit an exception to a destination as a message response.
		
		    This method is used to serialize a TransverseException as a response
		    to a failed evaluation or resolution request.
		###
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_MESSAGE_ERROR)
		MessageID.serialize(messageID, outStream)
		error.serializeConstructor(this, outStream)
		outStream.commit()
	
	transmitGeneralError : (destination, error) ->
		### Transmit an exception to a destination.
		
		    This method is probably not ever useful. It is used to signal a
		    general fault on the remote connection. Since even the most insecure
		    public server will want to ignore such Exception, due to the high
		    potential for abuse, this would probably be used on a client where
		    the server is fully trusted.
		###
		outStream = destination.getOutputBuffer()
		outStream.write(headers.HEADER_GENERAL_ERROR)
		error.serializeConstructor(this, outStream)
		outStream.commit()
	
	##
	# Error handling
	##
	
	handleIncomingMessageError : (destination, messageID, error) ->
		### Handler for an Exception raised on an incoming Eval/Resolve.
		
		    Handler for the situation when an incoming message (an eval or
		    resolve) has triggered an error, such that the error in question
		    should be sent as an error reply as a response to the message.
		###
		if not (error isinstance TransverseException)
			@bus.handleLocalException(destination, error)
		else
			@transmitMessageError(destination, messageID, error)
