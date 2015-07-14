from ripley.service import *
from ripley.serialize import *

__all__ = [
	"Test",
	"EchoService"]

class Test(PassByReference):
	@staticmethod
	def getProxyClass():
		return TestProxy


class TestConstructorProxy(EvaluationProxy):
	@staticmethod
	def serializeArguments(cxn, args, outStream):
		Int32.serialize(args[0], outStream)
	@staticmethod
	def deserializeReturn(cxn, inStream):
		return cxn.deserializeObject(inStream, Test)

@implements(Test)
class TestProxy(ObjectProxy):
	class echo(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			UnicodeString.serialize(args[0], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = UnicodeString.deserialize(inStream)
			ret1 = Int32.deserialize(inStream)
			return ret0, ret1
	
	echo = echo(b"Test::echo")
	

class TestExposed(ExposedObject):
	class constructor(ExposedCall):
		transverseID = b"Test"
		def __call__(self, cxn, inStream, outStream):
			arg0 = Int32.deserialize(inStream)
			__self__ = self.call(arg0)
			cxn.serializeObject(__self__, outStream)
	
	class echo(ExposedCall):
		transverseID = b"Test::echo"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, Test)
			arg0 = UnicodeString.deserialize(inStream)
			ret0, ret1 = self.call(__self__, arg0)
			UnicodeString.serialize(ret0, outStream)
			Int32.serialize(ret1, outStream)
	
	exposedMethods = {
		"constructor" : constructor,
		"echo" : echo
	}

class EchoService(Service):
	transverseID = b"@784dd132"
	Test = TestConstructorProxy(b"Test")
	@classmethod
	def getExposed(cls):
		return exposedOnEchoService


exposedOnEchoService = {
	"Test" : TestExposed
}


