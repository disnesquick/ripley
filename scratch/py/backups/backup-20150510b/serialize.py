import struct
from abc import ABCMeta

def implements(interface):
	""" Convienient function to handle the registration of the fact that a class
	    is an implementation of an interface.
	"""
	def inner(implementation):
		interface.register(implementation)
		return implementation
	return inner


class PassByReference:
	""" This is the root class for all of those derived data-types that can be
	    sent across the gateway "by-reference". Note that these objects do not
	    have to be single-dispatch pythonic objects just objects that can be
	    kept locally but referenced remotely.
	"""


class PassByValue:
	pass


class ComplexPassByValue(PassByValue):
	pass


class Null(PassByValue):
	@staticmethod
	def serialize(value, outStream):
		pass

	@staticmethod
	def deserialize(inStream):
		return None


class Tuple(ComplexPassByValue):
	@classmethod
	def serialize(cls, obj, gateway, outStream):
		gateway.serializeObjects(obj, cls.subTypes, outStream)

	@classmethod
	def deserialize(cls, gateway, inStream):
		return gateway.deserializeObjects(cls.subTypes, inStream)


class MetaTuple(type):
	def __new__(mcls, subTypes):
		return super().__new__(mcls, "DerivedTuple", (Tuple,), {"subTypes":subTypes})


class Int32(PassByValue):
	@staticmethod
	def serialize(value, outStream):
		outStream.write(struct.pack(">i",value))
	
	@staticmethod
	def deserialize(inStream):
		return struct.unpack(">i", inStream.read(4))[0]
	

class UnicodeString(PassByValue):
	@staticmethod
	def serialize(value, outStream):
		outStream.write(value.encode("UTF-8"))
		outStream.write(b"\x00")

	@staticmethod
	def deserialize(inStream):
		b = inStream.read(1)
		a = b""
		while b != b"\x00" and b!=b"":
			a = a + b
			b = inStream.read(1)
		return a.decode("UTF-8")


class TransverseID(PassByValue):
	@staticmethod
	def serialize(value, outStream):
		outStream.write(value)
		outStream.write(b"\x00")

	@staticmethod
	def deserialize(inStream):
		b = inStream.read(1)
		a = b""
		while b != b"\x00" and b!=b"":
			a = a + b
			b = inStream.read(1)
		return a

class SerialID(PassByValue):
	@staticmethod
	def integerToBytes(val):
		output = []
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
	def serialize(value, outStream):
		outStream.write(value)

	@staticmethod
	def deserialize(inStream):
		c = b = inStream.read(1)
		while b[0] & 0x80:
			b = inStream.read(1)
			c += b
		return c

class MessageID(SerialID):
	pass

class ObjectID(SerialID):
	@staticmethod
	def deserialize(inStream):
		return SerialID.deserialize(inStream) , SerialID.deserialize(inStream)

	@staticmethod
	def serialize(value, outStream):
		outStream.write(value[0])
		outStream.write(value[1])
