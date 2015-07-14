from scope import *

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
		builtinTypeMap[name] = BasicType(name)
	
	for name in builtinComplexTypes:
		builtinTypeMap[name] = ComplexType(name)
	
	#TODO: Move this into the compiler!
	builtinTypeMap["GetMyConnection"].implicitSerialization = True
	
	return builtinTypeMap



def buildOutput(processed, oHandle):
	oHandle.write("from ripley.service import *\n")
	oHandle.write("from ripley.serialize import *\n\n\n")
	
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
		outputClassConstructor(classDef, oHandle)
		outputProxyClass(classDef, oHandle)
	for func in processed.functions:
		outputProxyFunction(func, oHandle)
	for service in processed.services:
		outputService(service, oHandle)
	
	# Write out exposure classes
	for classDef in processed.classes:
		outputExposedClass(classDef, oHandle)
	for func in processed.functions:
		outputExposedFunction(func, oHandle)
	for service in processed.services:
		outputServiceExposed(service, oHandle)


def outputAbstract(abstract, oHandle):
	""" Write out the class definition of an 'abstract class'.
	
	    An abstract class is a serializable type which can be passed by
	    reference but admits no interface whatsoever. Basically allows
	    a 'local' object to be passed back and forth inside a blackbox.
	"""
	string = ("class %s(PassByReference):\n"
	          "\tpass\n\n\n")
	pars = (abstract.name,)
	oHandle.write(string%pars)


def outputClassBase(classdef, oHandle):
	string = ("class %s(PassByReference):\n"
	          "\t@staticmethod\n"
	          "\tdef getProxyClass():\n"
	          "\t\treturn %sProxy\n\n\n")
	pars = (classdef.name,classdef.name)
	oHandle.write(string%pars)


def outputExposedFunction(func, oHandle):
	string, pars = formatExposedCall(func, "Exposed", "")
	string = string%tuple(pars)
	oHandle.write(string[:-2])
	oHandle.write("\n\n")


def outputProxyFunction(func, oHandle):
	string, pars = formatProxyCall(func, "Proxy", "", False)
	oHandle.write(string%tuple(pars))
	oHandle.write("\n\n")


def outputClassConstructor(classdef, oHandle):
	for method in classdef.methods:
		if method.name == "constructor":
			break
	else:
		return
	substring = ["class %sConstructorProxy(EvaluationProxy):\n"]
	pars = [classdef.name]
	substring.append("\t@staticmethod\n")
	substring.append("\tdef serializeArguments(cxn, args, outStream):\n")
	inner = []
	for idx,(_,parType) in enumerate(method.params):
		argStr = "args[%d]"%idx
		inner.append(argSerialize(parType, argStr, "\t\t"))
	if (inner == [""] or inner == []) and not isMethod:
		inner = ["\t\tpass\n"]
	substring += inner
	
	substring.append("\t@staticmethod\n")
	substring.append("\tdef deserializeReturn(cxn, inStream):\n")
	substring.append("\t\treturn cxn.deserializeObject(inStream, %s)\n")
	pars.append(classdef.name)
	string = "".join(substring)
	oHandle.write(string%tuple(pars))
	oHandle.write("\n")


def outputExposedClass(classdef, oHandle):
	oHandle.write("class %sExposed(ExposedObject):\n"%classdef.name)
	for method in classdef.methods:
		string, pars = formatExposedCall(method, "", "\t", classdef)
		oHandle.write(string%tuple(pars))
	oHandle.write("\texposedMethods = {\n")
	inner = []
	for method in classdef.methods:
		inner.append("\t\t\"%s\" : %s" % (method.name, method.name))
	oHandle.write(",\n".join(inner))
	oHandle.write("\n\t}\n\n\n")


def outputProxyClass(classdef, oHandle):
	oHandle.write("@implements(%s)\n"%classdef.name)
	oHandle.write("class %sProxy(ObjectProxy):\n"%classdef.name)
	flag = False
	for method in classdef.methods:
		if method.name == "constructor":
			continue
		flag = True
		string, pars = formatProxyCall(method, "", "\t", True)
		string = string +("\t\n\t%s = %s(b\"%s\")\n\t\n")
		pars.append(method.name)
		pars.append(method.name)
		pars.append(method.transverseID)
		string = string%tuple(pars)
		oHandle.write(string)
	if not flag:
		oHandle.write("\tpass\n")
	oHandle.write("\n\n")


def outputServiceExposed(service, oHandle):
	oHandle.write("exposedOn%s = {\n"%service.name)
	substring = []
	pars = []
	for member in service.members:
		substring.append("\t\"%s\" : %sExposed")
		pars.append(member.name)
		pars.append(member.name)
	oHandle.write((",\n".join(substring))%tuple(pars))
	oHandle.write("\n}\n\n\n")


def outputService(service, oHandle):
	string = ("class %s(Service):\n"
	          "\ttransverseID = b\"%s\"\n")
	pars = [service.name, service.transverseID]
	
	#Proxy members
	for member in service.members:
		if isinstance(member, Function):
			string += "\t%s = %sProxy(b\"%s\")\n"
			pars.append(member.name)
			pars.append(member.name)
			pars.append(member.transverseID)
		elif isinstance(member, ClassType):
			for method in member.methods:
				if method.name == "constructor":
					break
			else:
				continue
			string += "\t%s = %sConstructorProxy(b\"%s\")\n"
			pars.append(member.name)
			pars.append(member.name)
			pars.append(member.transverseID)
	
	string += "\t@classmethod\n"
	string += "\tdef getExposed(cls):\n"
	string += "\t\treturn exposedOn%s\n\n\n"
	pars.append(service.name)

	oHandle.write(string%tuple(pars))


def formatExposedCall(method, post = "", indent = "", owner = None):
	if owner is not None and method.name == "constructor":
		isConstructor = True
	else:
		isConstructor = False
	string = ("%sclass %s(ExposedCall):\n"
	          "%s\ttransverseID = b\"%s\"\n")
	pars = [indent, method.name + post, indent, method.transverseID]
	
	if isinstance(method, Evaluation) or isConstructor:
		substring = ["\tdef __call__(self, cxn, inStream, outStream):\n"]
	else:
		substring = ["\tdef __call__(self, cxn, inStream):\n"]
	caller = []
	if owner is not None and not isConstructor:
		substring.append("\t\t__self__ = cxn.deserializeObject(inStream, %s)\n")
		pars.append(owner.name)
		caller.append("__self__")
	for idx,(_,parType) in enumerate(method.params):
		argStr = "arg%d"%idx
		substring.append(argDeserialize(parType, argStr, "\t\t"))
		caller.append(argStr)
	
	if isinstance(method, Evaluation) and len(method.returns) > 0:
		retter = []
		for idx,(_,parType) in enumerate(method.returns):
			retter.append("ret%d"%idx)
		retStr = ", ".join(retter)
		argStr = ", ".join(caller)
		substring.append("\t\t%s = self.call(%s)\n"%(retStr,argStr))
		for idx,(_,parType) in enumerate(method.returns):
			retStr = "ret%d"%idx
			substring.append(argSerialize(parType, retStr, "\t\t"))
	elif method.name == "constructor" and owner is not None:
		argStr = ", ".join(caller)
		substring.append("\t\t__self__ = self.call(%s)\n")
		substring.append("\t\tcxn.serializeObject(__self__, outStream)\n")
		pars.append(argStr)
	else:
		argStr = ", ".join(caller)
		substring.append("\t\tself.call(%s)\n")
		pars.append(argStr)
	
	string += indent + indent.join(substring) + "\t\n"
	return string, pars


def formatProxyCall(method, post = "", indent = "\t", isMethod = True):
	if isMethod:
		former = "Method"
		instArg = "inst, "
	else:
		instArg = former = ""
		
	if isinstance(method, Notification):
		substring = ["class %s%s(%sNotificationProxy):\n"]
	else:
		substring = ["class %s%s(%sEvaluationProxy):\n"]
	pars = [method.name, post, former]
	
	substring.append("\t@staticmethod\n")
	substring.append("\tdef serializeArguments(cxn, %sargs, outStream):\n")
	pars.append(instArg)
	if isMethod:
		substring.append("\t\tReference.serialize(inst.reference, outStream)\n")
	inner = []
	for idx,(_,parType) in enumerate(method.params):
		argStr = "args[%d]"%idx
		inner.append(argSerialize(parType, argStr, "\t\t"))
	if (inner == [""] or inner == []) and not isMethod:
		inner = ["\t\tpass\n"]
	substring += inner
	
	if isinstance(method, Evaluation):
		substring.append("\t@staticmethod\n")
		substring.append("\tdef deserializeReturn(cxn, inStream):\n")
		retter = []
		for idx,(_,parType) in enumerate(method.returns):
			argStr = "ret%d"%idx
			substring.append(argDeserialize(parType, argStr, "\t\t"))
			retter.append(argStr)
		substring.append("\t\treturn %s\n")
		pars.append(", ".join(retter))
	return indent + indent.join(substring), pars


def argSerialize(parType, argStr, indent = "\t"):
	if parType.implicitSerialization:
		return ""
	if isinstance(parType, BasicType):
		return "%s%s.serialize(%s, outStream)\n" % (indent, parType.name,
		                                            argStr)
	if isinstance(parType, ComplexType):
		return "%s%s.serialize(cxn, %s, outStream)\n" % (indent, parType.name,
		                                                 argStr)
	else:
		return "%scxn.serializeObject(%s, outStream)\n" % (indent, argStr)


def argDeserialize(parType, argStr, indent = "\t"):
	if isinstance(parType, BasicType):
		return "%s%s = %s.deserialize(inStream)\n" % (indent, argStr,
		                                              parType.name)
	elif isinstance(parType, ComplexType):
		return "%s%s = %s.deserialize(cxn, inStream)\n" % (indent, argStr,
		                                              parType.name)
	else:
		return "%s%s = cxn.deserializeObject(inStream, %s)\n" % (
		                                           indent, argStr, parType.name)
