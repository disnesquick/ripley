from zlib import crc32

__all__ = ["ParseScope", "BasicType", "ComplexType", "AbstractType",
           "ClassType", "ServiceType", "ExceptionType",
           "Evaluation", "Notification", "Function"]


class NameSuffix:
	def __init__(self, string):
		self.string = string
	def __get__(self, instance, owner):
		return instance.name + self.string


class Override:
	def __init__(self, lang):
		self.lang = lang
	def __get__(self, instance, owner):
		return instance.name + self.string



class Type:
	def __init__(self, name, compiler):
		self.name = name
		self.compiler = compiler
	

class BasicType(Type):
	pass


class ComplexType(Type):
	pass


class AbstractType(Type):
	pass


class ExceptionType(Type):
	def __init__(self, name, compiler, params):
		super().__init__(name, compiler)
		self.params = params


class ClassType(Type):
	def __init__(self, name, compiler, methods):
		super().__init__(name, compiler)
		self.transverseID = name
		self.methods = methods
		for method in methods:
			if method.name == "constructor":
				method.transverseID = "%s"%name
			else:
				method.transverseID = "%s::%s"%(name, method.name)


class ServiceType(Type):
	def __init__(self, name, memberList):
		super().__init__(name, None)
		self.members = memberList
		tmp = (".".join(i.transverseID for i in memberList)).encode()
		self.transverseID = "@%x"%(crc32(tmp)&0xffffffff)


class Value:
	def __init__(self, name):
		self.transverseID = "::%s"%name
		self.name = name


class Function(Value):
	pass


class Evaluation(Function):
	def __init__(self, name, params, returns):
		super().__init__(name)
		self.params = params
		self.returns = returns


class Notification(Function):
	def __init__(self, name, params):
		super().__init__(name)
		self.params = params


class ParseScope:
	def __init__(self, parents = None, typeBaseMap = None):
		if parents is None:
			if typeBaseMap is None:
				raise Exception("No parents and no base map")
			else:
				self.parents = []
				self.typeMap = typeBaseMap
		else:
			self.parents = parents
			self.typeMap = {}
		self.valueMap = {}
	
	def hasType(self, key):
		if key in self.typeMap:
			return True
		else:
			return any(parent.hasType(key) for parent in self.parents)
	
	def addType(self, typedef):
		self.typeMap[typedef.name] = typedef
	
	def getType(self, typeName):
		if typeName in self.typeMap:
			return self.typeMap[typeName]
		for parent in self.parents:
			try:
				return parent.getType(typeName)
			except KeyError:
				pass
		raise KeyError
	
	def hasValue(self, key):
		if key in self.valueMap:
			return True
		else:
			return any(parent.hasValue(key) for parent in self.parents)
	
	def addValue(self, value):
		self.valueMap[value.name] = value
	
	def getValue(self, valueName):
		if valueName in self.valueMap:
			return self.valueMap[valueName]
		for parent in self.parents:
			try:
				return parent.getValue(valueName)
			except KeyError:
				pass
		raise KeyError
	
	def addParent(self, scope):
		self.parents.append(scope)
