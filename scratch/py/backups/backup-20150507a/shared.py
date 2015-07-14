import asyncio
from collections import Callable
import inspect
import io
import struct
from serialize import *
from abc import ABCMeta

class Transverse:
	""" Base class for transverse objects. A transverse object is one that exists universally
	    and consistently across the space of end-points. It is therefore predicated on two
	    components.
	     1. A consistent interface such that its behaviour is guaranteed independent of
	        platform.
	     2. A universal identifier, such that is can be recalled by any end-point that knows
	        of it.
	"""
	def __init__(self, ident):
		self.__transverse_id__ = ident.encode("UTF-8")


class TransverseCallInterface(Transverse):
	""" Class that represents a function call, a fundamental unit of communication in an RPC
	    library. Consists of the type-definition of the parameters and the return-type. This
	    includes reference to those types which are shared objects, i.e. those types which
	    are transmitted by reference/proxy rather than directly.
	"""
	def __init__(self, ident, funcInterface):
		super().__init__(ident)
		if not isinstance(funcInterface, Callable):
			raise(TypeError("%s expects a Callable, received a %s [%s]"%(type(self), type(funcInterface), funcInterface)))

	@staticmethod
	def decodeReturnTypes(returnTypes):
		""" Given the pythonic returnType, which could be a tuple, this function will
		    go through and check that the returnType conforms to a standard pattern of
		    serializable entities and returns a valid tuple of types.
		"""
		if returnTypes is inspect._empty:
			# Replace empty return type with empty tuple
			returnTypes = (Null,)
		elif not isinstance(returnTypes, tuple):
			# Fold single return type into tuple
			returnTypes = (returnTypes,)

		# Ensure that all types are serializible
		for arg in returnTypes:
			if not issubclass(arg, SerializableType):
				raise(SyntaxError("return type %s was not a SerializableType"%type(arg)))

		return returnTypes

	@staticmethod
	def decodePositionalTypes(args):
		""" Given the python call decorators, this will process them into a form of
		    positional list, which can then be used for serializing or deserializing.
		"""
		positionalTypes = tuple()
		for argName, arg in args:
			# Ensure that all the arguments are serializable
			if not issubclass(arg.annotation, SerializableType):
				raise(SyntaxError("%s does not have a SerializableType annotation [%s]"%(argName, arg.annotation)))
			if arg.kind == arg.POSITIONAL_OR_KEYWORD:
				positionalTypes += arg.annotation,
			# Ensure that no variadic arguments are used
			elif arg.kind in [arg.KEYWORD_ONLY, arg.VAR_POSITIONAL, arg.VAR_KEYWORD]:
				raise(SyntaxError("Variadic arguments are not allowed in RemoteCalls"))
			else:
				raise(Exception("Unexpected arg kind %s"%arg.kind))
		return positionalTypes

	@staticmethod
	def buildReferencingList(typList, idx=0):
		""" Go through a typle-list and build a list of those objects which must be
		    transmitted by reference/proxy. This is then used for fast referencing and
		    dereferencing of those objects/IDs.
		"""
		build = []
		for typ in typList:
			if issubclass(typ, ShareByReference):
				build.append(idx)
			idx += 1
		return build

	def translateInterface(self, funcInterface, method = False):
		""" Takes a python function object and converts it into a pair of type-lists
		    (for the return type and the parameter type) as well as a function which will
		    convert a python call into an argument list.
		"""
		# Grab the type-list from the callable's signature
		signature = inspect.signature(funcInterface)
		args = iter(signature.parameters.items())
		if method:
			next(args)
		return signature.bind, self.decodePositionalTypes(args), self.decodeReturnTypes(signature.return_annotation)

	
class TransverseMethodInterface(TransverseCallInterface):
	""" An interface for a single-dispatch method which is a member of an interface class.
	"""
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		super().__init__(universalIdentifier, funcInterface)
		# Ensure argument sanity
		self.argBinder, self.positionalTypes, self.returnTypes = self.translateInterface(funcInterface, True)
		self.positionalTypes = (selfTypeClass,) + self.positionalTypes
		self.argumentIndices = self.buildReferencingList(self.positionalTypes)
		self.returnIndices = self.buildReferencingList(self.returnTypes)

	def getProxy(self):
		""" Returns a proxy method for this interface, which can then be used to 
		    transmit calls across to another end-point.
		"""
		return MethodProxy(self)


class TransverseConstructorInterface(TransverseCallInterface):
	""" An interface for a constructor, which is used to instantiate an instance of an
	    interface class.
	"""
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		TransverseCallInterface.__init__(self, universalIdentifier, funcInterface)
		# Ensure argument sanity
		self.returnTypes = (selfTypeClass,)
		self.argBinder, self.positionalTypes, _ = self.translateInterface(funcInterface, False)
		self.argumentIndices = self.buildReferencingList(self.positionalTypes)
		self.returnIndices = self.buildReferencingList(self.returnTypes)
	
	def getProxy(self):
		""" Returns a proxy constructor for this interface, which can then be used to 
		    transmit calls across to another end-point.
		"""
		return ConstructorProxy(self)


class CallProxy:
	""" Base class for proxy calls; these represent function calls that are serialized and
	    transmitted across a gateway, with subsequent return of arguments.
	"""
	# TODO: Notifications
	def __init__(self, iface):
		self.iface = iface

	@asyncio.coroutine
	def doCall(self, gateway, args):
		iface = self.iface
		resolvedCall = (yield from gateway.resolveTransverse(iface))
		args = gateway.bindArgumentSerialization(iface, args)
		def reply(byteStream):
			returnTuple = gateway.deserializeResponse(iface, byteStream)
			if len(returnTuple) == 1:
				return returnTuple[0]
			else:
				return returnTuple
		return (yield from gateway.transceiveEval(resolvedCall, args, reply))


class MethodProxy(CallProxy):
	""" MethodProxy is used to replace methods in proxy objects, it acts
	    as a stub to bind an instance to an interface call
	"""
	class Bound:
		def __init__(self, remoteInstance, callProxy):
			self.__self__ = remoteInstance
			self.callProxy = callProxy
	
		@asyncio.coroutine
		def __call__(self, *args, **kwargs):
			proxy = self.callProxy
			__self__ = self.__self__
			args = proxy.iface.argBinder(__self__, *args, **kwargs).args
			return (yield from proxy.doCall(__self__.gateway, list(args)))

	def __get__(self, instance, owner):
		return self.Bound(instance, self)


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
		def callOn(self, gateway):
			""" Sends the argument-bound call to a specific gateway for execution
			    on the remote end.
			"""
			proxy = self.callProxy
			args = proxy.iface.argBinder(*self.args, **self.kwargs).args
			return (yield from proxy.doCall(gateway, list(args)))

		@asyncio.coroutine
		def __rlshift__(self, other):
			return (yield from self.callOn(other))

	def __call__(self, *args, **kwargs):
		return self.Call(self, args, kwargs)


class ShareByReference(ObjectID):
	""" This is the root class for all of those derived data-types that can be
	    sent across the gateway "by-reference". Note that these objects do not
	    have to be single-dispatch pythonic objects just objects that can be
	    kept locally but referenced remotely.
	"""


class MetaTransverseObjectInterface(ABCMeta):
	""" This is the root object metaclass for those 'objects' which can be shared across
	    a gateway. This is actually just a convienience, since nearly all supported
	    language support smalltalk-style single-dispatch objects it makes sense
	    to include a convienient method of access.
	    Interfaces only support single inheritance, since this is the lowest
	    common denominator.
	"""
	allowedSpecialNames = {"__constructor__", "__module__","__qualname__", "__doc__"}
	def __init__(cls, name, bases, nameSpace):
		super().__init__(name, bases, nameSpace)
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

		# Add the constructor if one has been specified
		if "__constructor__" in nameSpace:
			cons = TransverseConstructorInterface(cls, cls.__constructor__, objUUID)
			cls.__iface_members__["__constructor__"] = cons

		cls.__proxy_class__ = None

	def getProxyClass(cls):
		""" Grabs a proxy class for a particular interface, if it has already been
		    generated otherwise generate first and then return it. Proxy classes are
		    always set to be implementations of the interface they are derived from.
		"""
		# Generated cached proxy class if it is not present
		if cls is TransverseObjectInterface:
			return ProxyObject

		if cls.__proxy_class__ is None:
			proxyParents = [base.getProxyClass() for base in cls.__bases__ if isinstance(base, MetaTransverseObjectInterface)]
			if len(proxyParents) > 1:
				raise(TyperError("Only single inheritance for interfaces is supported"))
			proxyName = cls.__name__ + "Proxy"
			nameSpace = {"__constructor__":None}
			nameSpace.update({key:value.getProxy() for key,value in cls.__iface_members__.items()})
			cls.__proxy_class__ = implements(cls)(type(proxyName, tuple(proxyParents), nameSpace))
		return cls.__proxy_class__

	def newRemote(cls, *args, **kwargs):
		""" Quick access to creation of a new object rather than going through
		    __iface_members__["__constructor__"]. It is also rather more self-documenting
		    than calling through this clumsy route.
		"""
		proxy = cls.getProxyClass()
		if proxy.__constructor__ is None:
			raise(Exception("Cannot construct a nonConstructable class"))
		return proxy.__constructor__(*args, **kwargs)


class TransverseObjectInterface(ShareByReference, metaclass = MetaTransverseObjectInterface):
	""" Base class for object interfaces. These interfaces are convieniences for using
	    single dispatch object semantics in suitable languages (most of them).
	"""
	def __constructor__():
		pass


class ProxyObject:
	""" Base class for proxy objects. Prxy objects are bound to a particular gateway with
	    an identifying reference ID, which is uesd to recognition on reception of an
	    incoming identification.
	"""
	def __init__(self, gateway, sharedReference):
		self.gateway = gateway
		self.__shared_id__ = sharedReference


def implements(interface):
	""" Convienient function to handle the registration of the fact that a class
	    is an implementation of a transverse interface.
	"""
	def inner(implementation):
		interface.register(implementation)
		return implementation
	return inner


class FilterElement(TransverseObjectInterface):
	""" This is the base class for all filter types, filters are objects
	    which are referenced by the FILTER message type to insert them
	    in the decoding chain between the transcoder and the transport.
	"""
