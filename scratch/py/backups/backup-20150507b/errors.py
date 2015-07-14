from shared import Transverse, TransverseConstructorInterface
from serialize import *


class MetaTransverseException(type):
	def __init__(cls, name, bases, nameSpace):
		if "__root_object__" in nameSpace:
			del nameSpace["__root_object__"]
			return

		objUUID = "XCPT::"+name

		if not "__constructor__" in nameSpace:
			raise(Exception("Transverse exceptions must define __constructor__"))
		
		cls.__iface_members__ = {"__constructor__":TransverseConstructorInterface(cls, cls.__constructor__, objUUID)}
		cls.__implementation_of__ = cls
		# TODO Old code: allows implementation of multiple targets in one
		# cls.__implementation_of__ = (cls, None)

class TransverseException(Transverse, Exception, metaclass = MetaTransverseException):
	__root_object__ = True
	def __init__(self, *args, **kwargs):
		self.args = args
		self.kwargs = kwargs

	def getBoundArgs(self, transportGateway):
		call = self.__iface_members__["__constructor__"]
		orderedArgs = call.argBinder(*self.args, **self.kwargs).args
		transportGateway.referenceShared(orderedArgs, call.argumentIndices)
		return EncodingTypeBinding(orderedArgs, call.positionalTypes)

	def __repr__(self):
		return "ERROR %s"%type(self).__name__

class UnknownError(TransverseException):
	def __constructor__():
		pass

class SerializedError(TransverseException):
	def __constructor__(string:UnicodeString):
		pass

class UnknownMessageIDError(TransverseException):
	def __constructor__(messageID:MessageID):
		pass

class UnknownTransverseIDError(TransverseException):
	def __constructor__(tranverseID:TransverseID):
		pass

class UnknownObjectIDError(TransverseException):
	def __constructor__(objectID:ObjectID):
		pass

class DecodingError(TransverseException):
	def __constructor__():
		pass

class EncodingError(TransverseException):
	def __constructor__():
		pass

class TransmissionError(TransverseException):
	def __constructor__():
		pass

class RemoteEndFailure(Exception):
	def __init__(self, error, handle):
		self.error = error
		self.handle = handle
	def __repr__(self):
		return "REMOTE AT %s was %s"%(self.handle, self.error)
