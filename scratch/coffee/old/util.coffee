### @declare util
###

Function::metaclass = (meta, metargs...) ->
	### metaclass creates an easy and clear way for the prototype of the class object to
	    be set and therefore for a kind of metaclassing to be applied
	###
	deepCopyMeta = (cls, mcls) ->
		# Deep copy function because we can't replace the constructor [[prototype]]
		if mcls isnt Object::
			deepCopyMeta(cls, Object.getPrototypeOf(mcls))
		for key, value of mcls
			cls[key] = value

	deepCopyMeta(@, meta.prototype)
	@__meta__ = meta
	meta.apply(@, metargs)


Function::mixin = (mixin, mixargs...) ->
	for key, value of mixin::
		@::[key] = value
	for key, value of mixin
		@[key] = value
	mixin.apply(@, mixargs)


Function::defineProperty = (prop, desc) ->
		Object.defineProperty @::, prop, desc


class MetaBase
	implements : (iface) ->
		@__implementation_of__ = iface


class StringIO
	constructor: (data) ->
		@value = if data then data else ""
		@pos = 0

	readByte: () ->
		@value.charCodeAt(@pos++)

	writeByte: (byte) ->
		@value += String.fromCharCode(byte)

	write: (string) ->
		@value += string

	read: (len) ->
		ret = @value.substring(@pos, @pos+len)
		@pos += len
		ret

	@defineProperty 'length',
		get: -> @value.length


stringToArrayBuffer = (str) ->
	buf = new ArrayBuffer(str.length)
	bufView = new Uint8Array(buf)
	for i in [0..str.length]
		bufView[i] = str.charCodeAt(i)
	buf

