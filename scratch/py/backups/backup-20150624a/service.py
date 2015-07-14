# System imports
import inspect

# Local imports
from .route     import *
from .serialize import *
from .share     import *
from .handshake import *

# Exports
__all__ = ["Service", "ServiceOfferingInterface", "ServiceOffering"]

class MetaService(type):
	""" MetaClass for the Service class.
	
	    On definition of a new Service class, the parents are inspected and
	    interfaces exposed by those parent Services are collated into a
	    dictionary. The properties of the class are theninspected and those that
	    are not special properties (i.e. With names surrounded by double
	    underscores '__property__') are added to the dictionary.
	"""
	def __init__(cls, name, bases, nameSpace):
		cls.serviceName = ("SERVICE::" + name).encode("utf-8")
		cls.exposedInterfaces = {}
		
		# Enumerate the interfaces from the parents and bundle them together
		# into this class's exposedInterfaces.
		for base in inspect.getmro(cls):
			if base not in (object, cls) and issubclass(base, Service):
				cls.exposedInterfaces.update(base.exposedInterfaces)
		
		# Enumerate the properties from this class and add them into the
		# the exposedInterfaces dictionary.
		for key,value in nameSpace.items():
			if key[0:2] != "__":
				cls.exposedInterfaces[key] = value
				setattr(cls, key, _CallableStub(value))
	
	def implementation(cls, **kwargs):
		""" Produce a ServiceImplementation object.
		
		    A ServiceImplementation object is produced from the current service
		    name, and member name/interface pairs. The names are used to match
		    the interfaces against the implementations, supplied as keyword
		    arguments.
		"""
		return ServiceImplementation(cls, **kwargs)
	
	def on(cls, connection):
		master = connection.bus.masterService
		busRemoteToken = master.discover(cls.serviceName)
		bus = connection.bus
		localRoute = OpenRoute(connection)
		master.connect(localRoute, busRemoteToken)
		
		return cls(localRoute.route)


class _CallableStub:
	def __init__(self, value):
		self.iface = value.getCallInterface()
		self.call = value.getBoundCallableClass()
		
	def __get__(self, instance, owner):
		return self.call(instance.destination, self.iface)


class Service(metaclass = MetaService):
	""" Base class for service objects.
	"""
	def __init__(self, destination):
		self.destination = destination


class ServiceImplementation:
	def __init__(self, service, **kwargs):
		self.serviceName = service.serviceName
		self.exposedTransverse = {}
		
		# Check that the objects provided as implementations and those present
		# as interfaces correspond to each other
		for name in kwargs:
			if not name in service.exposedInterfaces:
				raise(NotImplemented(name))
		for name in service.exposedInterfaces:
			if not name in kwargs:
				raise(NotImplemented(name))
		
		for name, obj in kwargs.items():
			# Grab the interface from the ServiceInterface class, the interface
			# should be the actual interface (i.e. extracted from the stack of
			# modifiers if such is present.
			iface = service.exposedInterfaces[name]
			while isinstance(iface, TransverseModifier):
				iface = iface.master
			
			# A TransverseObjectInterface should be exposed as an object
			# implementation.
			if isinstance(iface, type):
				if issubclass(iface, TransverseObjectInterface):
					self.exposeObjectImplementation(iface, obj)
			
			# A TransverseCallableInterface should be exposed as a call
			# implementation.
			elif isinstance(iface, TransverseCallableInterface):
				self.exposeCallImplementation(iface, obj)
			
			# Anything else cannot be exposed and results in an error.
			else:
				raise(TypeError(iface))
	
	def exposeObjectImplementation(self, iface, objcls):
		""" Exposes a TransverseObjectInterface on this Service.
		    
		    Exposes a python object that has been marked as an implementation of
		    an object to the other side(s) of the transport. If the interface is
		    marked as non-constructable, then no constructor method will be made
		    available.
		"""
		for name, member in iface.__iface_members__.items():
			# If the object has a constructor then expose the object class
			# itself as the basic call.
			if name == "__constructor__":
				call = objcls
			else:	
				call = getattr(objcls, name)
			while isinstance(member, TransverseModifier):
				member = member.master
			self.exposeCallImplementation(member, call)
	
	def exposeCallImplementation(self, iface, func):
		""" Exposes a function call func that conforms to the interface iface.
		"""
		uuid = iface.transverseID
		self.exposeTransverseObject(uuid, ExposedCallable(func, iface))
	
	def exposeTransverseObject(self, transverseID, obj):
		""" Exposes an object through a transverseID.
		"""
		self.exposedTransverse[transverseID] = obj
	
	def offerOn(self, connection, useSameConnection = True):
		""" Adds the service implementation and also notifies the bus master
		    that this service is being offered.
		"""
		connection.addTransverseMap(self.exposedTransverse)
		master = connection.bus.masterService
		offering = ServiceOffering(connection, useSameConnection)
		master.offer(offering, self.serviceName)


class ServiceOfferingInterface(TransverseObjectInterface):
	def request(self) -> OpenRouteInterface:
		pass


@implements(ServiceOfferingInterface)
class ServiceOffering:
	def __init__(self, connection, service, useSameConnection = True):
		self.connection = connection
		self.service = service
		self.useSame = useSameConnection
	
	def request(self):
		if self.useSame:
			return OpenRoute(self.connection)
		else:
			connection = self.connection.bus.connection()
			connection.handleService(self.service)
			return OpenRoute(connection) 
