### @declare error
  #
  # @require util
  # @require shared
###

class ShareableExceptionInterface extends ShareableObjectInterface
	constructor : (objUUID, parent, defList) ->
		objUUID = "XCPT::" + objUUID
		@__iface_members__ = {}

		# If there is a constructor on the definition list then add this with a special interface object
		if "constructor" of defList
			@__iface_members__.__constructor__ = new TransverseConstructorInterface(this, defList["constructor"], objUUID)
			delete defList.constructor
		
		@__proxy_class__ = null
		@parent = parent


class MetaTransverseException
	constructor : (constructorArguments) ->
		cls = @prototype
		callInterface = new ShareableExceptionInterface @name, null,
			constructor : new CallInterface [], constructorArguments
		cls.__implementation_of__ = callInterface
		cls.__constructor_args__ = constructorArguments
		cls.name = @name


class TransverseException extends Error
	@mixin MetaTransverseException, [UnicodeString]
	message : "NO MESSAGE DETAILS"
	constructor : (sendArgs=[]) ->
		@sendArgs = sendArgs
		@stack = (new Error).stack.split("\n")[1..].join("\n")

	getBoundArgs : () ->
		new EncodingTypeBinding(@sendArgs, @__constructor_args__)


class UnknownError extends TransverseException
	@mixin MetaTransverseException, []


class SerializedError extends TransverseException
	@mixin MetaTransverseException, [UnicodeString]
	constructor : (errorString, stack) ->
		super [errorString + "\n" + stack]
		# for debug purposes
		@message = "Stringified error: "+errorString


class UnknownMessageIDError extends TransverseException
	@mixin MetaTransverseException, [MessageID]
	constructor : (messageID) ->
		super [messageID]
		@messageID = messageID
		# for debug purposes
		@message = "Unknown ID: "+messageID


class UnknownTransverseIDError extends TransverseException
	@mixin MetaTransverseException, [TransverseID]
	constructor : (transverseID) ->
		super [transverseID]
		@transverseID = transverseID
		# for debug purposes
		@message = "Unknown ID: "+transverseID


class UnknownObjectIDError extends TransverseException
	@mixin MetaTransverseException, [ObjectID]
	constructor : (objectID) ->
		super [objectID]
		@objectID = objectID
		# for debug purposes
		@message = "Unknown ID: "+objectID


class DecodingError extends TransverseException
	@mixin MetaTransverseException, []
	

class EncodingError extends TransverseException
	@mixin MetaTransverseException, []


class TransmissionError extends TransverseException
	@mixin MetaTransverseException, []

class RemoteEndFailure extends Error
	name : "RemoteEndFailure"
	constructor : (err, remote) ->
		@err = err
		@remote = remote
		@message = "#{ @err.name } : #{ @err.message } \n\n #{ @err.stack }"
