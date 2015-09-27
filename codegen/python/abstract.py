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
