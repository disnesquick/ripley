### @declare serialize
  #
  # @require util
###

class SerializableType
	### Base class for all classes which support the encodeStatic
	    decodeStatic interface for transcoding.
	###

class NullStub extends SerializableType
	@decodeStatic: (inStream) ->
		null

class UInt32 extends SerializableType
	### Transcoding class for a 32-bit Unsigned Integer
	###

	@decodeStatic: (inStream) ->
		data1 = inStream.readByte()
		data2 = inStream.readByte()
		data3 = inStream.readByte()
		data4 = inStream.readByte()
		data1 << 24 + data2 << 16 + data3 << 8 + data4

	@encodeStatic: (value, outStream) ->
		data4 = value & 0xFF
		value >>= 8
		data3 = value & 0xFF
		value >>= 8
		data2 = value & 0xFF
		value >>= 8
		data1 = value & 0xFF
		outStream.writeByte(data1)
		outStream.writeByte(data2)
		outStream.writeByte(data3)
		outStream.writeByte(data4)


class Int32 extends SerializableType
	### Transcoding class for a 32-bit Signed Integer
	###

	@decodeStatic: (inStream) ->
		value = UInt32.decodeStatic(inStream)
		(value & ((1 << 31)-1)) - (value & (1 << 31))

	@encodeStatic: (value, outStream) ->
		value = (value & ((1 << 31) - 1)) + (value & (1 << 31))
		UInt32.encodeStatic(value, outStream)


class UnicodeString extends SerializableType
	### Transcoding class for a standard Unicode text string
	###

	@decodeStatic: (inStream) ->
		b = inStream.read(1)
		a = ""
		while b != "\x00" and b != ""
			a = a + b
			b = inStream.read(1)
		return a
	
	@encodeStatic: (value, outStream) ->
		outStream.write(value)
		outStream.write("\x00")


class TransverseID extends UnicodeString
	### Transcoding class for a Transverse object identifier
	###


class SerialID extends SerializableType
	### Transcoding base class for transmitted object identifiers
	###
	@integersToBytes: (vals...) ->
		output = ""
		for val in vals
			while val > 0x7F
				output += String.fromCharCode(val & 0x7F | 0x80)
				val >>= 7
			output += String.fromCharCode(val)
		output

	@encodeStatic: (value, outStream) ->
		outStream.write(value)

	@decodeStatic: (inStream) ->
		c = b = inStream.read(1)
		while b.charCodeAt(0) & 0x80
			b = inStream.read(1)
			c += b
		c


class MessageID extends SerialID
	### Transcoding class for message unique identifiers
	###


class ObjectID extends SerialID
	### Transcoding class for shared object identifiers
	###

	@decodeStatic: (inStream) ->
		SerialID.decodeStatic(inStream) + SerialID.decodeStatic(inStream)


class EncodingTypeBinding
	### Class to handle binding of a list of types to a list of values
	    for use in encoding those values to a serial stream
	###

	constructor: (objectTuple, typeTuple) ->
		@objectTuple = objectTuple
		@typeTuple = typeTuple
		@zipped = ([objectTuple[i], typeTuple[i]] for i in [0..objectTuple.length-1])
	

class DecodingTypeBinding
	### Class to handle binding of a list of types to an input stream
	    for use in decoding a serial stream to a list of values
	###

	constructor: (dataStream, typeTuple) ->
		@dataStream = dataStream
		@typeTuple = typeTuple
