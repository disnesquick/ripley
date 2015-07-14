# System imports
import random

# External imports
from unstuck import *

# Local imports
from .share     import *
from .serialize import *
from .service   import *
from .handshake import *

# Exports
__all__ = ["BusMasterInterface", "BusMaster", "BusMasterService",
           "busMasterService", "busClientService"]

class BusMasterInterface(TransverseObjectInterface):
	def getNeonateID(self) -> ConnectionID:
		pass
	
	def offer(self, offer:ServiceOfferingInterface, name:TransverseID):
		pass
	
	def discover(self, name:TransverseID) -> SerialID:
		pass
	
	def connect(self, localRoute:OpenRouteInterface, remoteToken:SerialID):
		pass
	
	@notification
	def requestConnection(self, request:OpenTransportInterface,
	                            remoteBusID:BusID):
		pass
	
	def registerServer(self, server:TransportServer, outCode:TransverseID):
		pass

#TODO discover and connect to use a "share remote object" type interface

@implements(BusMasterInterface)
class BusMaster:
	def __init__(self, bus):
		self.bus = bus
		self.register = {}
		self.tokenRegistry = {}
		self.connectionCount = -1
		self.servers = {}
		self.waiting = {}
	
	def getNeonateID(self):
		self.connectionCount +=1
		connectID = SerialID.integerToBytes(self.connectionCount)
		return connectID
	
	def offer(self, offer, name):
		self.register[name] = offer
	
	def translateToken(self, token):
		while True:
			innerToken = random.getrandbits(32)
			innerToken = SerialID.integerToBytes(innerToken)
			if not innerToken in self.tokenRegistry:
				break
		self.tokenRegistry[innerToken] = token
		return innerToken
	
	def discover(self, name):
		serviceOffering = self.register[name]
		token = serviceOffering.request()
		return self.translateToken(token)
	
	def registerServer(self, server, outCode):
		if isinstance(server, ProxyObject):
			myBusID = server.destination.transport.remoteBusID
		else:
			myBusID = self.bus.busID
		self.servers[myBusID] = server, outCode
	
	def requestConnection(self, request, remoteBusID):
		if isinstance(request, ProxyObject):
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
	
	def connect(self, routeA, remoteToken):
		routeB = self.tokenRegistry[remoteToken]
		del self.tokenRegistry[remoteToken]
		
		if isinstance(routeA, ProxyObject):
			transportA = routeA.destination.transport
			transportTokenA = transportA.remoteBusID
		else:
			transportA = None
			transportTokenA = self.bus.busID
		connectionIDA = routeA.getConnectionID()
		
		if isinstance(routeB, ProxyObject):
			transportB = routeB.destination.transport
			transportTokenB = transportB.remoteBusID
		else:
			transportB = None
			transportTokenB = self.bus.busID
		connectionIDB = routeB.getConnectionID()
		
		if isinstance(routeA, ProxyObject) and isinstance(routeB, ProxyObject):
			localTokenA = routeA.supplyEndpointBus.async(transportTokenB)
			localTokenB = routeB.supplyEndpointBus.async(transportTokenA)
			localTokenA = await(localTokenA)
			localTokenB = await(localTokenB)
		elif isinstance(routeB, ProxyObject):
			localTokenB = routeB.supplyEndpointBus.async(transportTokenA)
			localTokenA = routeA.supplyEndpointBus(transportTokenB)
			localTokenB = await(localTokenB)
		elif isinstance(routeA, ProxyObject):
			localTokenA = routeA.supplyEndpointBus.async(transportTokenB)
			localTokenB = routeB.supplyEndpointBus(transportTokenA)
			localTokenA = await(localTokenA)
		else:
			localTokenA = routeA.supplyEndpointBus(transportTokenB)
			localTokenB = routeB.supplyEndpointBus(transportTokenA)
		routeA.completeRoute(localTokenB, connectionIDB)
		routeB.completeRoute(localTokenA, connectionIDA)


@transverseDef
def getBusMasterInterface(connection: GetMyConnection) -> (BusMasterInterface):
	pass


def getBusMaster(connection):
	return connection.bus.busMaster


class BusMasterService(Service):
	BusMaster    = BusMasterInterface
	getBusMaster = getBusMasterInterface


busMasterService = BusMasterService.implementation(
	BusMaster    = BusMaster,
	getBusMaster = getBusMaster)


class BusClientService(Service):
	OpenRoute           = OpenRouteInterface
	ServiceOffering     = ServiceOfferingInterface
	OpenTransport       = OpenTransportInterface


busClientService = BusClientService.implementation(
	OpenRoute           = OpenRoute,
	ServiceOffering     = ServiceOffering,
	OpenTransport       = OpenTransport)
