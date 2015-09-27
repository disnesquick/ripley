from scope import *
from .compilers import *
from .abstract import *
from .proxy import *
from .exposed import *
from .service import *

__all__ = [
	"ObjectCompiler",
	"AbstractCompiler",
	"ExceptionCompiler",
	"buildBaseMap",
	"buildOutput"]


def buildBaseMap():
	builtinBasicTypes = [
		"URI", "ConnectionID", "BusID", "RouteToken",
		"ObjectID", "TransverseID", "Reference", "MessageID",
		"Int8",  "Int16",  "Int32",  "Int64",
		"UInt8", "UInt16", "UInt32", "UInt64",
		"ByteString", "UnicodeString"
	]
	
	builtinComplexTypes = [
		"Tuple", "GetMyConnection"
	]
	
	builtinTypeMap = {}
	
	for name in builtinBasicTypes:
		builtinTypeMap[name] = BasicType(name, BasicCompiler(name, False))
	
	for name in builtinComplexTypes:
		builtinTypeMap[name] = ComplexType(name, BasicCompiler(name, True))
	
	builtinTypeMap["GetMyConnection"].compiler = BasicCompilerImplicitSerial(
	                                               "GetMyConnection", True)
	
	return builtinTypeMap


def buildOutput(processed, oHandle):
	oHandle.write("from ripley.serialize import *\n")
	oHandle.write("from ripley.interface import *\n")
	oHandle.write("from ripley.service import *\n\n\n")
	
	# Write out module exports
	oHandle.write("__all__ = [\n")
	inner = []
	for abstract in processed.abstract:
		inner.append("\t\"%s\""%abstract.name)
	for classDef in processed.classes:
		inner.append("\t\"%s\""%classDef.name)
	for service in processed.services:
		inner.append("\t\"%s\""%service.name)
	oHandle.write(",\n".join(inner))
	oHandle.write("]\n\n\n")
	
	# Write out abstract classes
	for abstract in processed.abstract:
		outputAbstract(abstract, oHandle)
	for classDef in processed.classes:
		outputClassBase(classDef, oHandle)
	
	# Write out proxy classes
	for classDef in processed.classes:
		outputProxyClass(classDef, oHandle)
	for func in processed.functions:
		outputProxyFunction(func, oHandle)
	
	# Write out exposure classes
	for classDef in processed.classes:
		outputExposedClass(classDef, oHandle)
	for func in processed.functions:
		outputExposedFunction(func, oHandle)
	
	# Write out the service classes
	for service in processed.services:
		outputService(service, oHandle)
	

