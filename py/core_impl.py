""" Module:  core_impl
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file implements the Ripley core interface given by core.idl
"""

# External imports
from unstuck import *

# Local imports
from . import core
from .core import BusMasterService, BusClientService
from .route import *
from .serialize import *

# Exports
__all__ = ["TransportServer", "OpenRoute", "OpenTransport", "BusMaster",
           "busMasterService", "busClientService", "BusMasterService",
           "BusClientService", "ServiceOffering"]

class TransportServer(core.TransportServer):
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


@implements(core.OpenTransport)
class OpenTransport:
	protocolMap = {}
	def __init__(self):
		self.future = Future()
	
	def connect(self, code, shiboleth):
		protocol, arg = code.split("://")
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


@implements(core.OpenRoute)
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


@implements(core.ServiceOffering)
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


class ProspectiveRoute(core.ProspectiveRoute):
	def __init__(self, remote):
		self.remote = remote


@implements(core.BusMaster)
class BusMaster:
	def __init__(self, bus):
		self.bus = bus
		self.register = {}
		self.connectionCount = -1
		self.servers = {}
		self.waiting = {}
	
	def getNeonateID(self):
		self.connectionCount +=1
		connectID = SerialID.integerToBytes(self.connectionCount)
		return connectID
	
	def offer(self, offer, name):
		self.register[name] = offer
	
	def discover(self, name):
		serviceOffering = self.register[name]
		token = serviceOffering.request()
		return ProspectiveRoute(token)
	
	def registerServer(self, server, outCode):
		if isinstance(server, ObjectProxy):
			myBusID = server.destination.transport.remoteBusID
		else:
			myBusID = self.bus.busID
		self.servers[myBusID] = server, outCode
	
	def requestConnection(self, request, remoteBusID):
		if isinstance(request, ObjectProxy):
			myBusID = request.destination.transport.remoteBusID
		else:
			myBusID = self.bus.busID
		#TODO make this a little more sensible
		shiboleth = await(self.awaitSecondConnection(myBusID, remoteBusID))
		if not myBusID in self.servers and not remoteBusID in self.servers:
			raise(Exception)
		
		if (myBusID in self.servers
		 and (not remoteBusID in self.servers or myBusID < remoteBusID)):
				server, _ = self.servers[myBusID]
				request.accept(server, shiboleth)
		else:
			_, code = self.servers[remoteBusID]
			request.connect(code, shiboleth)
		
	def generateShiboleth(self):
		return b"NOTRANDOM"
	
	@asynchronous
	def awaitSecondConnection(self, myBusID, remoteBusID):
		# Not thread safe
		if not (myBusID, remoteBusID) in self.waiting:
			self.waiting[(remoteBusID, myBusID)] = fut = Future()
			return (yield from fut)
		else:
			shiboleth = self.generateShiboleth()
			fut = self.waiting.pop((myBusID, remoteBusID))
			fut.setResult(shiboleth)
			return shiboleth
	
	def connect(self, routeA, routeBWrapped):
		routeB = routeBWrapped.remote
		
		if isinstance(routeA, ObjectProxy):
			transportA = routeA.destination.transport
			transportTokenA = transportA.remoteBusID
		else:
			transportA = None
			transportTokenA = self.bus.busID
		connectionIDA = routeA.getConnectionID()
		
		if isinstance(routeB, ObjectProxy):
			transportB = routeB.destination.transport
			transportTokenB = transportB.remoteBusID
		else:
			transportB = None
			transportTokenB = self.bus.busID
		connectionIDB = routeB.getConnectionID()
		
		if isinstance(routeA, ObjectProxy) and isinstance(routeB, ObjectProxy):
			localTokenA = routeA.supplyEndpointBus.async(transportTokenB)
			localTokenB = routeB.supplyEndpointBus.async(transportTokenA)
			localTokenA = await(localTokenA)
			localTokenB = await(localTokenB)
		elif isinstance(routeB, ObjectProxy):
			localTokenB = routeB.supplyEndpointBus.async(transportTokenA)
			localTokenA = routeA.supplyEndpointBus(transportTokenB)
			localTokenB = await(localTokenB)
		elif isinstance(routeA, ObjectProxy):
			localTokenA = routeA.supplyEndpointBus.async(transportTokenB)
			localTokenB = routeB.supplyEndpointBus(transportTokenA)
			localTokenA = await(localTokenA)
		else:
			localTokenA = routeA.supplyEndpointBus(transportTokenB)
			localTokenB = routeB.supplyEndpointBus(transportTokenA)
		routeA.completeRoute(localTokenB, connectionIDB)
		routeB.completeRoute(localTokenA, connectionIDA)


def getBusMaster(connection):
	return connection.bus.busMaster


busClientService = core.BusClientService.implementation(
	OpenTransport,
	OpenRoute,
	ServiceOffering
)


busMasterService = core.BusMasterService.implementation(
	BusMaster,
	getBusMaster
)
