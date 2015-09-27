class PyCompiler:
	pass


class ObjectCompiler(PyCompiler):
	def __init__(self, name):
		self.parName = name
		self.deserial = "%s = cxn.deserializeObject(inStream, %s)\n" % ("%s",name)
		self.serial = "cxn.serializeObject(%s, outStream)\n"
	
	def outputSerial(self, indent, name):
		return indent + self.serial % name
	
	def outputDeserial(self, indent, name):
		return indent + self.deserial % name


AbstractCompiler = ExceptionCompiler = ObjectCompiler


class BasicCompiler(PyCompiler):
	""" Compiler for raw types
	
	    This class encapsulates the compilation of those types which will
	    be addressed in parameter lists as basic python types.
	"""
	def __init__(self, name, complexType = False):
		self.parName = name
		if complexType:
			self.deserial = "%s = %s.deserialize(cxn, inStream)\n" % ("%s", name)
			self.serial = "%s.serialize(%s, cxn, outStream)\n" % (name, "%s")
		else:
			self.deserial = "%s = %s.deserialize(inStream)\n" % ("%s", name)
			self.serial = "%s.serialize(%s, outStream)\n" % (name, "%s")
	
	def outputSerial(self, indent, name):
		return indent + self.serial % name
	
	def outputDeserial(self, indent, name):
		return indent + self.deserial % name


class BasicCompilerImplicitSerial(BasicCompiler):
	def outputSerial(self, indent, name):
		return ""



