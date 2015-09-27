from scope import *

def outputService(service, oHandle):
	""" Output python code for a service proxy object.
	
	    This function accepts an intermediate description of a service
	    definition and outputs the Service class definition for it.
	"""
	# Header for service, including inheritance from Service object.
	string = ("class %s(Service):\n"
	          "\ttransverseID = b\"%s\"\n")
	pars = [service.name, service.transverseID]
	
	# Enumerate service members and create the apropriate hooks.
	for member in service.members:
		# Global service functions are exposed as CallProxy instances.
		if isinstance(member, Function):
			string += "\t%s = %sProxy(b\"%s\")\n"
			pars += [member.name, member.name, member.transverseID]
		
		# Constructable classes are exposed as ConstructorProxy instances.
		elif isinstance(member, ClassType):
			if hasConstructor(member):
				string += "\t%s = %sConstructorProxy(b\"%s\")\n"
				pars += [member.name, member.name, member.transverseID]
	
	# Add the exposed object retrieval handle.
	exposed = formatExposedService(service)
	string += "\t@classmethod\n"
	string += "\tdef getExposed(cls):\n"
	string += "\t\treturn %s\n\n\n"
	pars.append(exposed)
	
	oHandle.write(string%tuple(pars))


def formatExposedService(service, indent = "\t\t"):
	""" Output python code for exposed service members.
	
	    This function accepts an intermediate representation of a service
	    definition and outputs the exposedService object for it.
	"""
	substring = []
	pars = []
	
	# Enumerate all members as key/value pairs.
	for member in service.members:
		substring.append("%s\t\"%s\" : %sExposed")
		pars.append(indent)
		pars.append(member.name)
		pars.append(member.name)
	
	return "{\n%s\n%s}"%((",\n".join(substring))%tuple(pars), indent)
