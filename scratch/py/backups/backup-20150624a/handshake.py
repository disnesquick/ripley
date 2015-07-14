# External imports
from unstuck import *

# Local imports
from .share     import *
from .serialize import *
from .route     import *

# Exports
__all__ = ["OpenTransportInterface", "OpenTransport", "OpenRoute",
           "OpenRouteInterface", "TransportServer"]

class TransportServer(BlackBox):
	def __init__(self, connectionURI):
		self.acceptanceTokens = {}
		self.entryShiboleth = None
		self.connectionURI = connectionURI
	
	def entryServer(self, entryConnection):
		self.entryShiboleth = b"hello-entry"
		self.entryConnection = entryConnection
	
	@asynchronous
	def acceptIncoming(self, shiboleth):
		fut = Future()
		# TODO timeout on the shiboleth
		self.acceptanceTokens[shiboleth] = fut
		return fut


class OpenTransportInterface(TransverseObjectInterface):
	@notification
	def accept(self, server:TransportServer, shiboleth:TransverseID):
		pass
	
	@notification
	def connect(self, code:BuswideID, shiboleth:TransverseID):
		pass


@implements(OpenTransportInterface)
class OpenTransport:
	protocolMap = {}
	def __init__(self):
		self.future = Future()
	
	def connect(self, code, shiboleth):
		protocol, arg = code.decode().split("://")
		method = type(self).protocolMap[protocol.lower()]
		transport = method(arg, shiboleth)
		self.future.setResultFast(transport)
	
	def accept(self, server, shiboleth):
		transport = await(server.acceptIncoming(shiboleth))
		self.future.setResultFast(transport)
	
	def awaitTransport(self):
		return await(self.future)
	
	@classmethod
	def registerProtocol(cls, name, method):
		cls.protocolMap[name.lower()] = method


class OpenRouteInterface(TransverseObjectInterface):
	""" The Transverse interface for the OpenRoute class.
	
	    See OpenRoute for full details.
	"""
	def supplyEndpointBus(self, busID: BusID) -> RouteToken:
		pass
	
	def completeRoute(self, remoteShiboleth:RouteToken,
	                        remoteConnectionID:ConnectionID):
		pass
	
	def getConnectionID(self) -> ConnectionID:
		pass


@implements(OpenRouteInterface)
class OpenRoute:
	""" A `potential' Route, to be reified by external processes.
	
	    The `Route' object is not used directly. When a process wishes to open
	    a Route, it expresses this intention through the creation of an
	    OpenRoute, this class. An OpenRoute is a Transverse object, so it can
	    be handed to a bus master, to fill in the remote End-point, although
	    the local end-point must be filled in by a local process. An OpenRoute
	    must be supplied with three components. These are:
	
	    1. A local connection, either on creation of the OpenRoute or
	       subsequently. This also supplies the local Bus.
	    2. A remote Bus.
	    3. Routing shiboleths from the remote Bus to the remote Connection.
	"""
	def __init__(self, connection = None):
		if connection is not None:
			self.connection = connection
		self.closed = False
	
	def supplyEndpointBus(self, busID):
		""" Supply the unique ID for the remote Bus.
		
		    This function will attempt to negotiate a Transport connection from
		    the local Bus to the remote Bus.
		"""
		bus = self.connection.bus
		transport = bus.resolveTransport(busID)
		return self.supplyTransport(transport)
	
	def supplyTransport(self, transport):
		""" Directly supply a Transport (used by bootstrap).
		
		    The Bus bootstrap protocol will supplies various details across a
		    a Transport, without a full Route having been established. Thus,
		    in this case, a Transport must be supplied directly and not
		    through the resolution via a bus's routing table. This is the only
		    valid instance of using this method.
		"""
		if not self.closed:
			self.route = Route(transport)
			return self.route.token
		else:
			raise(Exception)
	
	def supplyConnection(self, connection):
		""" Supply the origin Connection on the local Bus.
		"""
		self.connection = connection
	
	def completeRoute(self, remoteShiboleth, remoteConnectionID):
		""" Supply the remote routing components beyond the remote Bus.
		
		    This function completes the OpenRoute into a functional Route
		    object. This is accomplished by providing the remote shiboleth,
		    which is the binary code supplied to a Transport to ensure routing
		    beyond the remote Bus, and the remote Connection unique ID.
		"""
		if not self.closed:
			self.route.setOrigin(self.connection)
			self.route.setDestination(remoteShiboleth, remoteConnectionID)
			self.closed = True
		else:
			raise(Exception)
	
	def getConnectionID(self):
		""" Retrieve the unique ID of the local Connection.
		"""
		return self.connection.connectionID
