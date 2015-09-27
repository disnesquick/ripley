from scope import *

def outputProxyClass(classdef, oHandle):
	if hasConstructor(classdef):
		formatClassConstructor(classDef, oHandle)
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


def outputProxyFunction(func, oHandle):
	""" Output python code for a single proxy global function.
	
	    This function accepts an intermediate description of a global function
	    and outputs the CallProxy class definition for it.
	"""
	string, pars = formatProxyCall(func, "Proxy", "", False)
	oHandle.write(string%tuple(pars))
	oHandle.write("\n\n")


def formatClassConstructor(classdef, oHandle):
	substring = ["class %sConstructorProxy(EvaluationProxy):\n"]
	pars = [classdef.name]
	substring.append("\t@staticmethod\n")
	substring.append("\tdef serializeArguments(cxn, args, outStream):\n")
	inner = []
	for idx,(_,parType) in enumerate(method.params):
		argStr = "args[%d]"%idx
		inner.append(parType.compiler.outputSerial("\t\t", argStr))
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
		inner.append(parType.compiler.outputSerial("\t\t", argStr))
	if (inner == [""] or inner == []) and not isMethod:
		inner = ["\t\tpass\n"]
	substring += inner
	
	if isinstance(method, Evaluation):
		substring.append("\t@staticmethod\n")
		substring.append("\tdef deserializeReturn(cxn, inStream):\n")
		retter = []
		for idx,(_,parType) in enumerate(method.returns):
			argStr = "ret%d"%idx
			substring.append(parType.compiler.outputDeserial("\t\t",argStr))
			retter.append(argStr)
		substring.append("\t\treturn %s\n")
		pars.append(", ".join(retter))
	return indent + indent.join(substring), pars
