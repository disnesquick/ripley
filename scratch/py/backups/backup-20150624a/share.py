# System imports
from abc import ABCMeta
from collections import Callable
import inspect

# External imports
from unstuck import *

# Local imports
from .serialize import *

# Exports
__all__ = ["Transverse", "TransverseObjectInterface", 
           "TransverseCallableInterface", "TransverseModifier",
           "ExposedCallable", "transverseDef", "notification"]


class Transverse:
	""" Base class for transverse objects.
	
	    A transverse object is one that exists universally and consistently
	    across the space of end-points. It is therefore predicated on two
	    components.
	     1. A consistent interface such that its behaviour is guaranteed
	         independent of platform.
	     2. A universal identifier, such that is can be recalled by any
	         end-point that knows of it.
	"""
	def __init__(self, ident):
		self.transverseID = ident.encode("UTF-8")


class TransverseCallableInterface(Transverse):
	""" Encapsulation of a call interface, parameters and return value.
	
	    Class that represents a function call, a fundamental unit of
	    communication in an RPC library. Consists of the type-definition of the
	    parameters and the return-type. This includes reference to those types
	    which are shared objects, i.e. those types which are transmitted by
	    reference/proxy rather than directly.
	"""
	def __init__(self, funcInterface, ident):
		super().__init__(ident)
		if not isinstance(funcInterface, (Callable,FunctionModifyAnnotation)):
			raise(TypeError("%s expects a Callable, received a %s [%s]"
			               % (type(self), type(funcInterface), funcInterface)))
	
	@staticmethod
	def decodeReturnTypes(returnType):
		""" Given the pythonic returnType, which could be a tuple, this function
		    will go through and check that the returnType conforms to a standard
		    pattern of serializable entities and returns a valid tuple of types.
		"""
		if returnType is inspect._empty:
			return Null
		elif isinstance(returnType, tuple):
			# Ensure that all types are serializible
			for arg in returnType:
				annotation = arg
				# Implicit conversion of object interfaces
				if issubclass(annotation, TransverseObjectInterface):
					annotation = InterfaceReference(annotation)
				if not issubclass(annotation, (PassByReference, PassByValue)):
					raise(SyntaxError("return type %s was"
					                  " not a PassByValue"%type(arg)))
			return MetaTuple(returnType)
		else:
			return returnType
	
	@staticmethod
	def decodeParameterTypes(args):
		""" Given the python call decorators, this will process them into a form
		    of positional list, which can then be used for serializing or
		    deserializing.
		"""
		positionalTypes = tuple()
		for argName, arg in args:
			# Ensure that all the arguments are serializable
			annotation = arg.annotation
			# Implicit conversion of object interfaces
			if issubclass(annotation, TransverseObjectInterface):
				annotation = InterfaceReference(annotation)
			if not issubclass(annotation, (PassByReference, PassByValue)):
				raise(SyntaxError("%s does not have a PassByValue"
				                  " annotation [%s]"%(argName, arg.annotation)))
			varKinds = (arg.KEYWORD_ONLY, arg.VAR_POSITIONAL, arg.VAR_KEYWORD)
			if arg.kind == arg.POSITIONAL_OR_KEYWORD:
				positionalTypes += annotation,
			# Ensure that no variadic arguments are used
			elif arg.kind in varKinds:
				raise(SyntaxError("Variadic arguments are not"
				                  " allowed in RemoteCalls"))
			else:
				raise(Exception("Unexpected arg kind %s"%arg.kind))
		return positionalTypes
	
	def translateInterface(self, funcInterface, method = False):
		""" Takes a python function object and converts it into a pair of
		    type-lists (for the return type and the parameter type) as well as a
		    function which will convert a python call into an argument list.
		"""
		# Grab the type-list from the callable's signature
		signature = inspect.signature(funcInterface)
		args = iter(signature.parameters.items())
		if method:
			next(args)
		par = self.decodeParameterTypes(args)
		ret = self.decodeReturnTypes(signature.return_annotation)
		return signature.bind, par, ret
	
	def serializeArguments(self, connection, args, outStream):
		""" Serialize arguments through a connection to a stream.
		"""
		connection.serializeObjects(args, self.parameterTypes, outStream)
	
	def deserializeArguments(self, connection, inStream):
		return connection.deserializeObjects(self.parameterTypes, inStream)
	
	def serializeResult(self, connection, arg, outStream):
		connection.serializeObject(arg, self.returnType, outStream)
	
	def deserializeResult(self, connection, inStream):
		return connection.deserializeObject(self.returnType, inStream)


def InterfaceReference(reference):
	neonate = type("Ref:"+reference.__name__,
	               (PassByReference,),
	               {"getProxyClass":reference.getProxyClass})
	return neonate


class TransverseModifier:
	""" Base class for transverse modifiers.
	
	    A transverse modifer is an annotation added to an interface to specify
	    a certain kind of behaviour. For example, to specify that a method
	    should be handled as a notification, rather than an evaluation, a
	    TransverseNotificationModifier would be wrapped around the interface.
	"""
	def __init__(self, master):
		self.master = master
	
	def getCallInterface(self):
		return self.master.getCallInterface()


class TransverseNotificationModifier(TransverseModifier):
	def getBoundCallableClass(self):
		return self.master.getBoundCallableClass().toNotification()
	
	def getProxy(self):
		master = self.master.getProxy()
		return master.toNotification()


class TransverseFunctionInterface(TransverseCallableInterface):
	""" Subroutine interface.
	
	    An interface for a simple call, which will be handled as an evaluation.
	""" 
	def __init__(self, funcInterface, universalIdentifier):
		super().__init__(funcInterface, universalIdentifier)
		(self.argBinder,
		 self.parameterTypes,
		 self.returnType)     = self.translateInterface(funcInterface, False)
	
	def getBoundCallable(self, route):
		return BoundEvaluation(route, self)
	
	def getBoundCallableClass(self):
		return BoundEvaluation
	
	def getCallInterface(self):
		return self


class TransverseMethodInterface(TransverseCallableInterface):
	""" Instance-method interface.
	
	    An interface for a single-dispatch method which is a member of an
	    interface class.
	"""
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		super().__init__(funcInterface, universalIdentifier)
		# Ensure argument sanity
		(self.argBinder,
		 self.parameterTypes,
		 self.returnType)     = self.translateInterface(funcInterface, True)
		self.parameterTypes = (selfTypeClass,) + self.parameterTypes
	
	def getProxy(self):
		""" Returns a proxy method for this interface, which can then be used to
		    transmit calls across to another end-point.
		"""
		return MethodProxy(self)


class TransverseConstructorInterface(TransverseCallableInterface):
	""" Instance-constructor interface.
	    
	    An interface for a constructor, which is used to instantiate an instance
	    of an interface class.
	"""
	def __init__(self, selfTypeClass, funcInterface, universalIdentifier):
		super().__init__(funcInterface, universalIdentifier)
		# Ensure argument sanity
		self.returnType = selfTypeClass
		(self.argBinder, self.parameterTypes,
		  _) = self.translateInterface(funcInterface, False)


# Helper functions for specifying functions as interfaces.
#
# The following are `helper' functions that are used to wrap a function
# definition in the various Transverse interface specification objects.
# These should be used instead of the direct class instantiations as they
# are more literate.
#

# Specifiy that a function is actually a subroutine interface
def transverseDef(funcInterface):
	return TransverseFunctionInterface(funcInterface,
	                                   "CALL::%s" % funcInterface.__name__)

# Specify that a function interface should be called by notification rather
# than by evaluation.
def notification(iface):
	if isinstance(iface, (TransverseModifier, TransverseFunctionInterface)):
		return TransverseNotificationModifier(iface)
	else:
		return FunctionModifyAnnotation(iface,TransverseNotificationModifier)


class FunctionModifyAnnotation:
	def __init__(self, func, cls):
		self.func = func
		self.cls = cls


class MetaTransverseObjectInterface(ABCMeta):
	""" This is the root object metaclass for those 'objects' which can be
	    shared across a gateway. This is actually just a convienience, since
	    nearly all supported language support smalltalk-style single-dispatch
	    objects it makes sense to include a convienient method of access.
	    Interfaces only support single inheritance, since this is the lowest
	    common denominator.
	"""
	allowedSpecialNames = {"__constructor__", "__module__","__qualname__",
	                       "__doc__"}
	def __init__(cls, name, bases, nameSpace):
		super().__init__(name, bases, nameSpace)
		cls.__iface_members__ = {}
		objUUID = "CALL::"+name
		cls.__proxy_class__ = None
		
		for name, member in nameSpace.items():
			#disallow special python methods...
			if name[0:2] != "__":
				memberUUID = "%s::%s"%(objUUID, name)
				wrapper = cls.getModifiers(TransverseMethodInterface,
				                           member, memberUUID)
				cls.__iface_members__[name] = wrapper
			elif name == "__init__" and bases==(PassByReference,):
				pass
			elif not name in type(cls).allowedSpecialNames:
				raise(SyntaxError("%s is a forbidden name in an"
				                  " interface, in %s"%(name, cls)))
		
		# Add the constructor if one has been specified
		if "__constructor__" in nameSpace:
			cons = TransverseConstructorInterface(cls,
			                                      cls.__constructor__,
			                                      objUUID)
			cls.__iface_members__["__constructor__"] = cons
	
	def getModifiers(cls, targetClass, member, UUID):
		if isinstance(member, FunctionModifyAnnotation):
			subMember = member.func
			wrapper = member.cls
			return wrapper(targetClass(cls, subMember, UUID))
		else:
			return targetClass(cls, member, UUID)
	
	def getProxyClass(cls):
		""" Get the proxy class for this interface.
		    
		    Grabs a proxy class for a particular interface, if it has already
		    been generated otherwise generate first and then return it. Proxy
		    classes are always set to be implementations of the interface they
		    are derived from.
		"""
		# Generated cached proxy class if it is not present
		if cls is TransverseObjectInterface:
			return ProxyObject
		
		if cls.__proxy_class__ is None:
			proxyParents = tuple(
			                 base.getProxyClass()
			                 for base in cls.__bases__
			                 if isinstance(base, MetaTransverseObjectInterface))
			if len(proxyParents) > 1:
				raise(TypeError("Only single inheritance for"
				                " interfaces is supported"))
			proxyName = cls.__name__ + "Proxy"
			nameSpace = {key:value.getProxy()
			             for key,value in cls.__iface_members__.items()
			             if key != "__constructor__"}
			proxyClass = type(proxyName, proxyParents, nameSpace)
			cls.__proxy_class__ = implements(cls)(proxyClass)
		return cls.__proxy_class__
	
	def getBoundCallable(cls, route):
		if "__constructor__" in cls.__iface_members__:
			constructor = cls.__iface_members__["__constructor__"]
			return BoundEvaluation(route, constructor)
		else:
			return None
	
	def getBoundCallableClass(cls):
		if "__constructor__" in cls.__iface_members__:
			return BoundEvaluation
		else:
			return None
	
	def getCallInterface(cls):
		if "__constructor__" in cls.__iface_members__:
			return cls.__iface_members__["__constructor__"]
		else:
			return None


class TransverseObjectInterface(TransverseCallableInterface,
	                            metaclass = MetaTransverseObjectInterface):
	""" Base class for object interfaces.
	
	    These interfaces are convieniences for using single dispatch object
	    semantics in suitable languages (most of them).
	"""
	def __constructor__():
		pass


class RemoteCall:
	""" A binding of arguments to an interface.
	
	    Representation of a call that can be sent to a remote server for
	    execution. Consists of a reference to the function interface and the
	    arguments that were invoked upon it, bound into the relevant function.
	"""
	def __init__(self, iface, args, kwargs):
		self.iface = iface
		self.args = iface.argBinder(*args, **kwargs).args


class RemoteEval(RemoteCall):
	""" A RemoteCall which is sent as an evaluation.
	"""
	@asynchronous
	def callOn(self, route):
		""" Sends the argument-bound call to a specific gateway for execution
		    on the remote end.
		"""
		connection = route.connection
		
		# Resolve the TransverseID to a CallID
		objectIDFuture = connection.transceiveResolve(route,
		                                              self.iface.transverseID)
		objectID = yield from objectIDFuture
		
		# Transmit the remote call
		outStream, inStreamFuture = connection.transceiveEval(route, objectID)
		self.iface.serializeArguments(connection, self.args, outStream)
		outStream.commit()
		
		# Wait for the reply and deserialize the return
		inStream = yield from inStreamFuture
		return self.iface.deserializeResult(connection, inStream)


class RemoteNotify(RemoteCall):
	""" A RemoteCall which is sent as a notification
	"""
	@asynchronous
	def callOn(self, route):
		connection = route.connection
		objectIDFuture = connection.transceiveResolve(
		                                 route, self.iface.transverseID)
		objectID = yield from objectIDFuture
		outStream = connection.transmitNotify(route, objectID)
		self.iface.serializeArguments(connection, self.args, outStream)
		outStream.commit()


class BoundCallable:
	def __init__(self, route, iface):
		self.route = route
		self.iface = iface
	
	def __call__(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return await(remoteCall.callOn(self.route))
	
	def async(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return async(remoteCall.callOn(self.route))
	
	def coro(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return remoteCall.callOn(self.route)



class BoundEvaluation(BoundCallable):
	def getCall(self, args, kwargs):
		return RemoteEval(self.iface, args, kwargs)
	
	@classmethod
	def toNotification(cls):
		return BoundNotification


class BoundNotification(BoundCallable):
	def getCall(self, args, kwargs):
		return RemoteNotify(self.iface, args, kwargs)


class BoundMethodEvaluation(BoundCallable):
	def __init__(self, remoteInstance, iface):
		self.__self__ = remoteInstance
		self.route = remoteInstance.destination
		self.iface = iface
	
	def getCall(self, args, kwargs):
		return RemoteEval(self.iface, (self.__self__,)+args, kwargs)


class BoundMethodNotification(BoundMethodEvaluation):
	def getCall(self, args, kwargs):
		return RemoteNotify(self.iface, (self.__self__,)+args, kwargs)


class ExposedCallable(PassByReference):
	""" This class is a simple wrapped that associates a python function func,
	    with a Ripley call interface iface for exposure across a route.
	"""
	def __init__(self, func, iface):
		self.func = func
		self.iface = iface
	
	def handleEval(self, connection, inStream, outStream):
		# Handle the argument marshalling
		args = self.iface.deserializeArguments(connection, inStream)
			
		# Do the function call
		returnData = self.func(*args)
		
		# Finally, bind the returned data and write it to the output
		self.iface.serializeResult(connection, returnData, outStream)
	
	def handleNotification(self, connection, inStream):
		# Handle the argument marshalling
		args = self.iface.deserializeArguments(connection, inStream)
		
		# Do the function call
		self.func(*args)
	
	def handleFetch(self, connection, inStream):
		# Handle the argument marshalling
		args = self.iface.deserializeArguments(connection, inStream)
			
		# Do the function call
		return self.func(*args)


class MethodProxy:
	""" MethodProxy is used to replace methods in proxy objects, it acts
	    as a stub to bind an instance to an interface call
	"""
	def __init__(self, iface):
		self.iface = iface
	
	def __get__(self, instance, owner):
		return BoundMethodEvaluation(instance, self.iface)
	
	def toNotification(self):
		return MethodNotifyProxy(self.iface)


class MethodNotifyProxy(MethodProxy):
	def __get__(self, instance, owner):
		return BoundMethodNotification(instance, self.iface)
