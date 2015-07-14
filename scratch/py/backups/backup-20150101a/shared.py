import asyncio
from collections import Callable
import inspect
import io
import struct
from serialize import *

class Transverse:
	def __init__(self, ident):
		self.__transverse_id__ = ident.encode("UTF-8")

class TransverseCallInterface(Transverse):
	def __init__(self, ident, funcInterface):
		super().__init__(ident)
		if not isinstance(funcInterface, Callable):
			raise(TypeError("%s expects a Callable, received a %s [%s]"%(type(self), type(funcInterface), funcInterface)))

	@staticmethod
	def decodeReturnTypes(returnTypes):
		if returnTypes is inspect._empty:
			returnTypes = tuple()
		elif not isinstance(returnTypes, tuple):
			returnTypes = (returnTypes,)
		for arg in returnTypes:
			if not issubclass(arg, SerializableType):
				raise(SyntaxError("return type %s was not a SerializableType"%type(arg)))

		return returnTypes

	@staticmethod
	def decodePositionalTypes(args):
		# Ensure that all the arguments are serializable
		# Ensure that no variadic arguments are used
		# Ensure that all defaults are given as None (since these will be remote-resolved)
		positionalTypes = tuple()
		for argName, arg in args:
			if not issubclass(arg.annotation, SerializableType):
				raise(SyntaxError("%s does not have a SerializableType annotation [%s]"%(argName, arg.annotation)))
			if arg.kind == arg.POSITIONAL_OR_KEYWORD:
				positionalTypes += arg.annotation,
			elif arg.kind in [arg.KEYWORD_ONLY, arg.VAR_POSITIONAL, arg.VAR_KEYWORD]:
				raise(SyntaxError("Variadic arguments are not allowed in RemoteCalls"))
			else:
				raise(Exception("Unexpected arg kind %s"%arg.kind))
		return positionalTypes

	@staticmethod
	def buildExpositionTranscoderList(typList, idx=0):
		build = []
		for typ in typList:
			if issubclass(typ, SharedObjectTypeClass):
				build.append(idx)
			idx += 1
		return build

	def translateInterface(self, selfTypeClass, funcInterface):
		# Grab the callable's signature
		signature = inspect.signature(funcInterface)
		args = iter(signature.parameters.items())
		if self.isMethod:
			next(args)
		return signature.bind, self.decodePositionalTypes(args), self.decodeReturnTypes(signature.return_annotation)

class TransverseMethodInterface(TransverseCallInterface):
	""" An interface for a single-dispatch method that is a member of
	    an interface class
	"""
	isMethod = True
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		super().__init__(universalIdentifier, funcInterface)
		# Ensure argument sanity
		self.argBinder, self.positionalTypes, self.returnTypes = self.translateInterface(selfTypeClass, funcInterface)
		self.positionalTypes = (selfTypeClass,) + self.positionalTypes
		self.argumentIndices = self.buildExpositionTranscoderList(self.positionalTypes)
		self.returnIndices = self.buildExpositionTranscoderList(self.returnTypes)

	def getProxyCall(self):
		return MethodProxy(self)

		
class TransverseConstructorInterface(TransverseCallInterface):
	isMethod = False
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		TransverseCallInterface.__init__(self, universalIdentifier, funcInterface)
		# Ensure argument sanity
		self.returnTypes = (selfTypeClass,)
		self.argBinder, self.positionalTypes, _ = self.translateInterface(selfTypeClass, funcInterface)
		self.argumentIndices = self.buildExpositionTranscoderList(self.positionalTypes)
		self.returnIndices = self.buildExpositionTranscoderList(self.returnTypes)
	
	def getProxyCall(self):
		return ConstructorProxy(self)


class CallProxy:
	""" Base class for proxy calls; these represent function calls that are serialized and
	    transmitted across a gateway, with subsequent return of arguments.
	"""
	# TODO: Notifications
	def __init__(self, iface):
		self.iface = iface

	@classmethod
	def addFilterClass(cls):
		cls.filterClass = type(cls.__name__+"WithFilter", (FilteredCallProxy, cls), {})

	@asyncio.coroutine
	def doCall(self, transportGateway, orderedArgs):
		iface = self.iface
		resolvedCall = (yield from transportGateway.resolveTransverse(iface))
		argDescriptor = iface.bindArgumentSerialization(transportGateway, orderedArgs)
		return (yield from transportGateway.transceiveEval(resolvedCall, argDescriptor, iface.deserializeResponse))

	def bindOutgoingFilter(self, filter):
		self.typeChain = self.iface.positionalTypes + (FilterTypeBindingKludge,)
		self.inChain = [filter]
		self.outChain = []
		self.__class__ = self.filterClass

	def bindIncomingFilter(self, filter):
		self.typeChain = (FilterTypeBindingKludge,) + self.iface.positionalTypes
		self.inChain = []
		self.outChain = [filter]
		self.__class__ = self.filterClass

	def bindFilterPair(self, outFilter, inFilter):
		self.typeChain = (FilterTypeBindingKludge,) + self.iface.positionalTypes + (FilterTypeBindingKludge,)
		self.inChain = [outFilter]
		self.outChain = [inFilter]
		self.__class__ = self.filterClass


class FilteredCallProxy:
	@asyncio.coroutine
	def doCall(self, transportGateway, orderedArgs):
		resolvedCall = (yield from transportGateway.resolveTransverse(self.iface))
		argDescriptor = self.bindArgumentSerialization(transportGateway, orderedArgs)
		return (yield from transportGateway.transceiveEval(resolvedCall, argDescriptor, self.iface.deserializeResponse))

	def bindArgumentSerialization(self, transportGateway, orderedArgs):
		transportGateway.referenceShared(orderedArgs, self.iface.argumentIndices)

		filterChain = []
		for outputFilter in self.outChain:
			filterChain.append(FilterOutputTypeBindingKludge(transportGateway, outputFilter))
		filterChain += orderedArgs
		for inputFilter in self.inChain:
			filterChain.append(FilterInputTypeBindingKludge(transportGateway, inputFilter))

		return EncodingTypeBinding(filterChain, self.typeChain)

	def bindOutgoingFilter(self, filter):
		self.inChain += [filter]
		self.typeChain = self.typeChain + (FilterTypeBindingKludge,)

	def bindIncomingFilter(self, filter):
		self.outChain += [filter]
		self.typeChain = (FilterTypeBindingKludge,) + self.typeChain

	def bindFilterPair(self, outFilter, inFilter):
		self.inChain += [outFilter]
		self.outChain += [inFilter]
		self.typeChain = (FilterTypeBindingKludge,) + self.typeChain + (FilterTypeBindingKludge,)


class MethodProxy(CallProxy):
	""" MethodProxy is used to replace methods in proxy objects, it acts
	    as a stub to bind an instance to an interface call
	"""
	class Bound:
		def __init__(self, remoteInstance, callProxy):
			self.remoteInstance = remoteInstance
			self.callProxy = callProxy
	
		@asyncio.coroutine
		def __call__(self, *args, **kwargs):
			orderedArgs = list(self.callProxy.iface.argBinder(self.remoteInstance, *args, **kwargs).args)
			return (yield from self.callProxy.doCall(self.remoteInstance.transportGateway,orderedArgs))

		def bindOutgoingFilter(self, *args, **kwargs):
			return self.callProxy.bindOutgoingFilter(*args, **kwargs)

		def bindIncomingFilter(self, *args, **kwargs):
			return self.callProxy.bindIncomingFilter(*args, **kwargs)

		def bindFilterPair(self, *args, **kwargs):
			return self.callProxy.bindFilterPair(*args, **kwargs)


	def __get__(self, instance, owner):
		return self.Bound(instance, self)

MethodProxy.addFilterClass()

class ConstructorProxy(CallProxy):
	""" ConstructorProxy is used to replace the object factory (in python this is
	    the class callable).  It acts as a stub to bind arguments into a remote call
	    object.
	"""
	class Call:
		def __init__(self, callProxy, args, kwargs):
			self.callProxy = callProxy
			self.args = args
			self.kwargs = kwargs
	
		@asyncio.coroutine
		def __rlshift__(self, transportGateway):
			orderedArgs = list(self.callProxy.iface.argBinder(*self.args, **self.kwargs).args)
			return (yield from self.callProxy.doCall(transportGateway, orderedArgs))

	def __call__(self, *args, **kwargs):
		return self.Call(self, args, kwargs)


class SharedObjectTypeClass(ObjectID):
	""" This is the root class for all of those derived data-types that can be
	    sent across the gateway "by-reference". Note that these objects do not
	    have to be single-dispatch pythonic objects just objects that can be
	    kept locally but referenced remotely.
	"""
	""" TODO old code allows implementations to implement multiple interfaces
	    but this doesn't really seem all that useful actually. Gonna keep the code
	    in the file for a little bit until it's clear one way or the other
	
	@classmethod
	def implementedBy(cls, obj):
		if hasattr(obj, "__implementation_of__"):
			imp = obj.__implementation_of__
			while imp is not None:
				imp, rest = imp
				if issubclass(imp, cls):
					return True
				imp = rest
		return False
	"""
	@classmethod
	def implementedBy(cls, obj):
		if hasattr(obj, "__implementation_of__"):
			return issubclass(obj.__implementation_of__, cls)
		else:
			return False

class MetaShareableObjectInterface(type):
	""" This is the root object metaclass for those 'objects' which can be shared across
	    a gateway. This is actually just a convienience, since nearly all supported
	    language support smalltalk-style single-dispatch objects it makes sense
	    to include a convienient method of access.
	"""
	allowedSpecialNames = {"__constructor__", "__module__","__qualname__", "__doc__"}
	def __init__(cls, name, bases, nameSpace):
		cls.__iface_members__ = {}
		objUUID = "CALL::"+name

		for name, member in nameSpace.items():
			#disallow special python methods...
			if name[0:2] != "__":
				memberUUID = "%s::%s"%(objUUID, name)
				wrapper = TransverseMethodInterface(cls, member, memberUUID)
				cls.__iface_members__[name] = wrapper
			elif not name in type(cls).allowedSpecialNames:
				raise(SyntaxError("%s is a forbidden name in an interface, in %s"%(name, cls)))

		if "__constructor__" in nameSpace:
			cls.__iface_members__["__constructor__"] = TransverseConstructorInterface(cls, cls.__constructor__, objUUID)
			del cls.__constructor__

		cls.__proxy_class__ = None

	def getProxyClass(cls):
		""" Grabs a proxy class for a particular interface, if it has already been generated
		    otherwise generate first and then return it. Proxy classes are always set to be
		    implementations of the interface they are derived from.
		"""
		# Generated cached proxy class if it is not present
		if cls is ShareableObjectInterface:
			return ProxyObject

		if cls.__proxy_class__ is None:
			proxyParents = [base.getProxyClass() for base in cls.__bases__ if isinstance(base, MetaShareableObjectInterface)]
			if len(proxyParents) > 1:
				raise(TyperError("Only single inheritance for interfaces is supported"))
			proxyName = cls.__name__ + "Proxy"
			nameSpace = {"__constructor__":None}
			nameSpace.update({key:value.getProxyCall() for key,value in cls.__iface_members__.items()})
			cls.__proxy_class__ = implements(cls)(type(proxyName, tuple(proxyParents), nameSpace))
		return cls.__proxy_class__

	def requestNew(cls, *args, **kwargs):
		""" Quick access to creation of a new object rather than going through
		    __iface_members__["__constructor__"]. It is also rather more self-documenting
		    than calling through this clumsy route.
		"""
		proxy = cls.getProxyClass()
		if proxy.__constructor__ is None:
			raise(Exception("Cannot construct a nonConstructable class"))
		return proxy.__constructor__(*args, **kwargs)


class ProxyObject:
	def __init__(self, gateway, sharedReference):
		self.transportGateway = gateway
		self.__shared_id__ = sharedReference


class ShareableObjectInterface(SharedObjectTypeClass, metaclass = MetaShareableObjectInterface):
	def __constructor__():
		pass


def implements(interface):
	""" TODO old code allows implementations to implement multiple interfaces
	    but this doesn't really seem all that useful actually. Gonna keep the code
	    in the file for a little bit until it's clear one way or the other
	
	def inner(implementation):
		if not hasattr(implementation, "__implementation_of__"):
			implementation.__implementation_of__ = None
		implementation.__implementation_of__ = (interface, implementation.__implementation_of__)
		return implementation
	return inner
	"""
	def inner(implementation):
		implementation.__implementation_of__ = interface
		return implementation
	return inner

def nonConstructable(interface):
	del interface.__iface_members__["__constructor__"]
	return interface

from filter import *
