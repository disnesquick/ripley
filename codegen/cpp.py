from scope import *

class CPPCompiler:
	pass


class ObjectCompiler(CPPCompiler):
	def __init__(self, name):
		self.parName = name + "&"
		self.typeName = name
		self.retName = name
		self.deserial = "%s = %s.deserializeObject(inStream)" % ("%s",name)
		self.serial = "cxn.serializeObject(%s, outStream)" % ("%s")


AbstractCompiler = ExceptionCompiler = ObjectCompiler

class RawTypeCompiler(CPPCompiler):
	""" Compiler for raw types, available natively in C++.
	
	    This class encapsulates the compilation of those types which will
	    be addressed in parameter lists as their raw C++ type.
	"""
	def __init__(self, name, nativeName, argByReference):
		self.parName = nativeName + "&" if argByReference else ""
		self.typeName = nativeName
		self.retName = nativeName
		self.deserial = "%s = %s::readFrom(inStream)" % ("%s", name)
		self.serial = "%s::writeTo(%s, outStream)" % (name, "%s")



def buildBaseMap():
	serviceObjectTypes = [
		"URI", "ConnectionID", "BusID", "RouteToken",
		"ObjectID", "TransverseID", "Reference", "MessageID"]
	
	typeTranslation = dict(
		Int8   = ("int8_t",   False),
		Int16  = ("int16_t",  False),
		Int32  = ("int32_t",  False),
		Int64  = ("int64_t",  False),
		UInt8  = ("uint8_t",  False),
		UInt16 = ("uint16_t", False),
		UInt32 = ("uint32_t", False),
		UInt64 = ("uint64_t", False),
		ASCIIString = ("std::string", True),
		ByteString = ("std::vector<uint8_t>", True),
		UnicodeString = ("std::wstring", True))
	
	builtinTypeMap = {}
	
	for key, (value, ref) in typeTranslation.items():
		compiler = RawTypeCompiler(key, value, ref)
		builtinTypeMap[key] = BasicType(key, compiler)
	
	for name in serviceObjectTypes:
		compiler = ObjectCompiler(name)
		builtinTypeMap[name] = BasicType(name, compiler)
	
	compiler = ObjectCompiler("!!TODO!!")
	builtinTypeMap["GetMyConnection"] = ComplexType(name, compiler)
	
	return builtinTypeMap


def buildOutput(processed, oHandle):
	oHandle.write("#include <ripley/service>\n")
	
	# Write out abstract classes
	for abstract in processed.abstract:
		outputAbstract(abstract, oHandle)
	for classDef in processed.classes:
		outputClassBase(classDef, oHandle)


def outputAbstract(abstract, oHandle):
	""" Write out the class definition of an 'abstract class'.
	
	    An abstract class is a serializable type which can be passed by
	    reference but admits no interface whatsoever. Basically allows
	    a 'local' object to be passed back and forth inside a blackbox.
	"""
	string = ("class %s : public PassByReference {\n"
	          "protected:\n"
	          "\tvirtual void __abstractClassKludge() override {};\n"
	          "};\n\n")
	
	pars = (abstract.name,)
	
	oHandle.write(string%pars)


def outputClassBase(classDef, oHandle):
	substring = ["class %sProxy;\n\n"
	             "class %s : public PassByReference {\n"
	             "public:\n"
	             "\ttypedef %sProxy ProxyClass;\n"]
	
	pars = (classDef.name,) * 3
	for method in classDef.methods:
		substring.append(formatMethodPrototype(method))
	substring.append("protected:\n")
	substring.append("\tvirtual void __abstractClassKludge() override {};\n")
	substring.append("};\n\n")
	oHandle.write("".join(substring) % pars)


def formatMethodPrototype(method):
	string = "\tvirtual %s %s(%s) = 0;\n"
	
	if isinstance(method, Evaluation):
		build = []
		if len(method.returns) > 1:
			for _,parType in method.returns:
				build.append(parType.compiler.retName)
			retString = "std::tuple<" + ",".join(build) + ">"
		elif len(method.returns) == 1:
			retString = method.returns[0][1].compiler.retName
		else:
			retString = "void"
	else:
		retString = "void"
	
	build = []
	for _,parType in method.params:
		build.append(parType.compiler.parName)
	parString = ", ".join(build)
	
	return string % (retString, method.name, parString)
	
