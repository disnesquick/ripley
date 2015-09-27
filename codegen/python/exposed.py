from scope import *

def outputExposedClass(classdef, oHandle):
	""" Output python code for an exposed transverse class definition.
	
	    This function accepts an intermediate description of a transverse class
	    and outputs the ExposedObject class definition for it. All member
	    methods are output as appropriate ExposedCall class members.
	"""
	# Create program logic for the class and its methods.
	oHandle.write("class %sExposed(ExposedObject):\n"%classdef.name)
	for method in classdef.methods:
		string, pars = formatExposedCall(method, "", "\t", classdef)
		oHandle.write(string%tuple(pars))
	
	# Format the list of exposed methods in this class.
	inner = []
	oHandle.write("\texposedMethods = {\n")
	for method in classdef.methods:
		inner.append("\t\t\"%s\" : %s" % (method.name, method.name))
	
	# Serialize output to file.
	oHandle.write(",\n".join(inner))
	oHandle.write("\n\t}\n\n\n")


def outputExposedFunction(func, oHandle):
	""" Output python code for a single exposed global function.
	
	    This function accepts an intermediate description of a global function
	    and outputs the ExposedCall class definition for it.
	"""
	string, pars = formatExposedCall(func, "Exposed", "")
	string = string % tuple(pars)
	
	# Serialize output to file.
	oHandle.write(string[:-2])
	oHandle.write("\n\n")


def formatExposedCall(method, post = "", indent = "", owner = None):
	""" Output python code for an exposed function hook.
	
	    This function accepts an intermediate representation of a transverse
	    method interface and outputs the ExposedCall class definition for it.
	"""
	isConstructor = False
	hasInstanceArgument = False
	returnValues = -1
	
	# Determine properties of this function call definition.
	if isinstance(method, Evaluation):
		returnValues = len(method.returns)
	if owner is not None:
		if method.name == "constructor":
			isConstructor = True
			returnValues = 1
		else:
			hasInstanceArgument = True
	
	# Definition header.
	string = ("%sclass %s(ExposedCall):\n"
	          "%s\ttransverseID = b\"%s\"\n")
	pars = [indent, method.name + post, indent, method.transverseID]
	
	# outStream is provided for Evaluation targets or constructors
	if returnValues > -1:
		substring = ["\tdef __call__(self, cxn, inStream, outStream):\n"]
	else:
		substring = ["\tdef __call__(self, cxn, inStream):\n"]
	
	caller = [] # Storage for argument marshalling
	
	# Instance argument for non-constructor methods
	if hasInstanceArgument:
		substring.append("\t\t__self__ = cxn.deserializeObject(inStream, %s)\n")
		pars.append(owner.name)
		caller.append("__self__")
	
	# Marshall the rest of the arguments.
	for idx,(_,parType) in enumerate(method.params):
		argStr = "arg%d"%idx
		substring.append(parType.compiler.outputDeserial("\t\t",argStr))
		caller.append(argStr)
	
	# Constructor returns an instance objects.
	if isConstructor:
		argStr = ", ".join(caller)
		substring.append("\t\t__self__ = self.call(%s)\n")
		substring.append("\t\tcxn.serializeObject(__self__, outStream)\n")
		pars.append(argStr)
	
	# Evaluation with actual return parameters returns those values.
	elif returnValues > 0:
		retter = []
		for idx,(_,parType) in enumerate(method.returns):
			retter.append("ret%d"%idx)
		retStr = ", ".join(retter)
		argStr = ", ".join(caller)
		substring.append("\t\t%s = self.call(%s)\n"%(retStr,argStr))
		for idx,(_,parType) in enumerate(method.returns):
			retStr = "ret%d"%idx
			substring.append(parType.compiler.outputSerial("\t\t", retStr))
	
	# Notifications and nul-return evaluations do not return anything.
	else:
		argStr = ", ".join(caller)
		substring.append("\t\tself.call(%s)\n")
		pars.append(argStr)
	
	# Build complete string and return it.
	string += indent + indent.join(substring) + "\t\n"
	return string, pars



