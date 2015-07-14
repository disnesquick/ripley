### @declare shared
  #
  # @require util
  # @require serialize
###


class CallInterface
	constructor: (ret, args...) ->
		@returnTypes = ret
		@paramTypes = args


class Transverse


class ProxyObject
	constructor : (gateway, sharedReference) ->
		@transportGateway = gateway
		@__shared_id__ = sharedReference


class Transverse
	constructor : (ident) ->
		@__transverse_id__ = ident


class TransverseCallInterface extends Transverse
	constructor : (ident, funcInterface) ->
		super ident
		if not funcInterface instanceof CallInterface
			throw new TypeError("#{ @constructor.name } expects a CallInterface, received a #{ @funcInterface.constructor.name } [#{ funcInterface }]")


class TransverseMethodInterface extends TransverseCallInterface
	### An interface for a single-dispatch method that is a member of
	    an interface class
	###
	constructor : (thisTypeClass, funcInterface, universalIdentifier) ->
		super universalIdentifier, funcInterface
		paramTypes = [thisTypeClass].concat(funcInterface.paramTypes)
		console.log("method",paramTypes)
		@argEncodeBinder = (instanceObject, argList) -> new EncodingTypeBinding([instanceObject.__shared_id__].concat(argList), paramTypes)
		@argDecodeBinder = (serialStream) -> new DecodingTypeBinding(serialStream, paramTypes)
		@retEncodeBinder = (resultList) -> new EncodingTypeBinding(resultList, funcInterface.returnTypes)
		@retDecodeBinder = (serialStream) -> new DecodingTypeBinding(serialStream, funcInterface.returnTypes)
		@returnTypes = funcInterface.returnTypes

	getProxyCall : ->
		call = @
		(args...) ->
			transportGateway = @transportGateway
			argDescriptor = call.argEncodeBinder(@, args)
			transportGateway.resolveTransverse(call)
			.then (resolvedCall) ->
				transportGateway.transceiveEval(resolvedCall,  argDescriptor, call.retDecodeBinder)


class ArgBoundCall
	constructor : (call, args) ->
		@call = call
		@args = call.argEncodeBinder(args)

	doCallOn : (transportGateway) ->
		self = @
		transportGateway.resolveTransverse(@call)
		.then (resolvedCall) ->
			transportGateway.transceiveEval(resolvedCall, self.args, self.call.retDecodeBinder)


class TransverseConstructorInterface extends TransverseCallInterface
	### An interface for a single-dispatch method that is a member of
	    an interface class
	###
	constructor : (thisTypeClass, funcInterface, universalIdentifier) ->
		super universalIdentifier, funcInterface
		@argEncodeBinder = (argList) -> new EncodingTypeBinding(argList, funcInterface.paramTypes)
		@argDecodeBinder = (serialStream) -> new DecodingTypeBinding(serialStream, [NullStub].concat(funcInterface.paramTypes))
		@retEncodeBinder = (resultList) -> new EncodingTypeBinding(resultList, [thisTypeClass])
		@retDecodeBinder = (serialStream) -> new DecodingTypeBinding(serialStream, [thisTypeClass])
		@returnTypes = [thisTypeClass]

	getProxyCall : ->
		call = @
		(args...) ->
			new ArgBoundCall(call, args)


class SharedObjectTypeClass
	implementedBy : (obj) ->
		if "__implementation_of__" of obj
			obj.__implementation_of__  is this
		else
			false
	encodeStatic : ObjectID.encodeStatic
	decodeStatic : ObjectID.decodeStatic


class ShareableObjectInterface extends SharedObjectTypeClass
	constructor : (objUUID, parent, defList) ->
		@objName = objUUID
		objUUID = "CALL::" + objUUID
		@__iface_members__ = {}
		# If there is a constructor on the definition list then add this with a special interface object
		if "constructor" of defList
			@__iface_members__.__constructor__ = new TransverseConstructorInterface(this, defList["constructor"], objUUID)
			delete defList.constructor
		
		# Add the construction of the methods to interface members
		for name, member of defList
			memberUUID = objUUID + "::" + name
			wrapper = new TransverseMethodInterface(this, member, memberUUID)
			@__iface_members__[name] = wrapper

		@__proxy_class__ = null
		@parent = parent

	getProxyClass : () ->
		### Grabs the proxy class for a particular interface, if it has already been generated
		    otherwise generate first and then return it. Proxy classes are always set to be
		    implementations of the interface they are derived from.
		###

		if @__proxy_class__ == null
			nameSpace = {}
			if @parent is null
				proxyParent = ProxyObject
			else
				proxyParent = @parent.getProxyClass()

			self = this
			class DerivedProxyObject extends proxyParent
				@metaclass MetaBase
				@implements self

			for name, member of @__iface_members__
				DerivedProxyObject::[name] = member.getProxyCall()
				
			@__proxy_class__ = DerivedProxyObject
		@__proxy_class__

	requestNew : (args...) ->
		proxy = @getProxyClass()
		proxy.prototype.__constructor__.apply(null, args)
