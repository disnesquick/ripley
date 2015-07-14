import struct

class SerializableType:
	pass


class Null(SerializableType):
	@staticmethod
	def encodeStatic(value, outStream):
		pass

	@staticmethod
	def decodeStatic(inStream):
		return None


class Tuple(SerializableType):
	@classmethod
	def encodeStatic(cls, value, outStream):
		for obj, typ in zip(value, cls.subTypes):
			typ.encodeStatic(obj, outStream)

	@classmethod
	def decodeStatic(cls, inStream):
		return tuple(typ.decodeStatic(inStream) for typ in cls.subTypes)


class MetaTuple(type):
	def __new__(mcls, subTypes):
		return super().__new__(mcls, "DerivedTuple", (Tuple,), {"subTypes":subTypes})


class Integer:
	pythonType = int


class Int32(Integer, SerializableType):
	@staticmethod
	def encodeStatic(value, outStream):
		outStream.write(struct.pack(">i",value))
	
	@staticmethod
	def decodeStatic(inStream):
		return struct.unpack(">i", inStream.read(4))[0]
	

class String:
	pythonType = str


class ByteString(SerializableType):
	pythonType = bytes


class UnicodeString(String, SerializableType):
	@staticmethod
	def encodeStatic(value, outStream):
		outStream.write(value.encode("UTF-8"))
		outStream.write(b"\x00")

	@staticmethod
	def decodeStatic(inStream):
		b = inStream.read(1)
		a = b""
		while b != b"\x00" and b!=b"":
			a = a + b
			b = inStream.read(1)
		return a.decode("UTF-8")

class EncodingTypeBinding:
	def __init__(self, objects, objectTypes):
		self.objectTuple = objects
		self.typeTuple = objectTypes

	def __iter__(self):
		return zip(self.objectTuple, self.typeTuple)

	def __repr__(self):
		return ",".join(["%s:%s"%i for i in self.zipped])


class DecodingTypeBinding:
	def __init__(self, dataStream, objectTypes):
		self.data = dataStream
		self.typeTuple = objectTypes


class TransverseID(SerializableType):
	@staticmethod
	def encodeStatic(value, outStream):
		outStream.write(value)
		outStream.write(b"\x00")

	@staticmethod
	def decodeStatic(inStream):
		b = inStream.read(1)
		a = b""
		while b != b"\x00" and b!=b"":
			a = a + b
			b = inStream.read(1)
		return a

class SerialID(SerializableType):
	@staticmethod
	def integersToBytes(*vals):
		output = []
		for val in vals:
			while val > 0x7F:
				output.append(val & 0x7F | 0x80)
				val >>= 7
			output.append(val)
		return bytes(output)

	@staticmethod
	def bytesToInteger(bStream):
		shift = 0
		b = 0x80
		curByte = iter(bStream)
		output = 0
		while b & 0x80:
			b = next(curByte)
			output += b << shift
			shift += 7
		return output

	@staticmethod
	def encodeStatic(value, outStream):
		outStream.write(value)

	@staticmethod
	def decodeStatic(inStream):
		c = b = inStream.read(1)
		while b[0] & 0x80:
			b = inStream.read(1)
			c += b
		return c

class MessageID(SerialID):
	pass

class ObjectID(SerialID):
	@staticmethod
	def decodeStatic(inStream):
		return SerialID.decodeStatic(inStream) + SerialID.decodeStatic(inStream)
