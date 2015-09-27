from unstuck import *
from .interface import *

class Service:
	""" Base class for service objects.
	"""
	def __init__(self, destination):
		self.destination = destination
	
	@classmethod
	def implementation(cls, *args, **kwargs):
		""" Produce a ServiceImplementation object.
		
		    A ServiceImplementation object is produced from the current service
		    name, and member name/interface pairs. The names are used to match
		    the interfaces against the implementations, supplied as keyword
		    arguments.
		"""
		for arg in args:
			kwargs[arg.__name__] = arg
		return ServiceImplementation(cls.transverseID, cls.getExposed(),
		                             **kwargs)
	
	@classmethod
	def on(cls, connection):
		from .core_impl import OpenRoute
		master = connection.bus.busMaster
		busRemoteToken = master.discover(cls.transverseID)
		localRoute = OpenRoute(connection)
		master.connect(localRoute, busRemoteToken)
		
		return cls(localRoute.route)


class ServiceImplementation:
	def __init__(self, transverseID, exposedInterfaces, **kwargs):
		self.transverseID = transverseID
		self.exposedTransverse = {}
		
		# Check that the objects provided as implementations and those present
		# as interfaces correspond to each other
		for name in kwargs:
			if not name in exposedInterfaces:
				raise(NotImplementedError(name))
		for name in exposedInterfaces:
			if not name in kwargs:
				raise(NotImplementedError(name))
		
		for name, obj in kwargs.items():
			# Grab the interface from the Service class
			iface = exposedInterfaces[name]
			
			# A TransverseObjectInterface should be exposed as an object
			# implementation.
			if issubclass(iface, ExposedObject):
				self.exposeObjectImplementation(iface, obj)
			
			# A TransverseCallableInterface should be exposed as a call
			# implementation.
			elif issubclass(iface, ExposedCall):
				self.exposeCallImplementation(iface, obj)
			
			# Anything else cannot be exposed and results in an error.
			else:
				raise(TypeError(iface))
	
	def exposeObjectImplementation(self, iface, objcls):
		""" Exposes an ExposedObject on this Service.
		    
		    Exposes a python object that has been marked as an implementation of
		    an object to the other side(s) of the transport. If the interface is
		    marked as non-constructable, then no constructor method will be made
		    available.
		"""
		for name, member in iface.exposedMethods.items():
			# If the object has a constructor then expose the object class
			# itself as the basic call.
			if name == "constructor":
				call = objcls
			else:	
				call = getattr(objcls, name)
			transverseID = member.transverseID
			self.exposeTransverse(transverseID, member(call))
	
	def exposeCallImplementation(self, iface, func):
		""" Exposes a function call func that conforms to the interface iface.
		"""
		self.exposeTransverse(iface.transverseID, iface(func))
	
	def exposeTransverse(self, transverseID, obj):
		""" Exposes an object through a transverseID.
		"""
		self.exposedTransverse[transverseID] = obj
	
	def offerOn(self, connection, useSameConnection = True):
		""" Adds the service implementation and also notifies the bus master
		    that this service is being offered.
		"""
		from .core_impl import ServiceOffering
		connection.addTransverseMap(self.exposedTransverse)
		master = connection.bus.busMaster
		offering = ServiceOffering(connection, useSameConnection)
		master.offer(offering, self.transverseID)
