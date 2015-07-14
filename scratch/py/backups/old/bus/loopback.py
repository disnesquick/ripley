import io
from . import Bus
from serialize import *
from connection import Connection
from random import random
from route import *
from bus_master import *

from unstuck import *

class TransportClosed(Exception):
	pass


class TransportBuffer(io.BytesIO):
	def __init__(self, bus, destinationCode):
		super().__init__()
		self.dc = destinationCode
		self.write(destinationCode)
		self.bus = bus
	
	def commit(self):
		return async(self.bus.send(self.getvalue()))


class LoopbackBus(Bus):
	def __init__(self):
		self.transport = Queue()
		self.connectionCount = -1
		self.connections = {}
		self.routeCount = 0
		self.routeEndpoints = {}
		self.pendingRoutes = {}
		super().__init__()
		self.masterConnection = Connection(self)
		self.masterConnection.handleService(busEntryService)
		self.masterConnection.handleService(busMasterService)
		self.masterNotifyEdge = self.getMasterEdge()
		notifyConnection = Connection(self)
		notifyRoute = Route(notifyConnection)
		notifyRoute.setOutput(self.masterNotifyEdge, None)
		self.notifyService = BusEntryService(notifyRoute)
	
	def register(self, connection):
		self.connectionCount +=1
		connectID = SerialID.integerToBytes(self.connectionCount)
		self.connections[connectID] = connection
		if self.connectionCount > 0:
			connection.handleService(busClientService)
		return connectID
	
	def getMaster(self, connection):
		if self.connectionCount > 1:
			routeNeonateToMaster = Route(connection)
			tokenMasterToNeonate, fut = self.openBusEdge(routeNeonateToMaster)
			self.notifyService.neonateNotification(tokenMasterToNeonate, None)
			await(fut)
			return BusMasterService(routeNeonateToMaster)
	
	def makeConnection(self, localToken, remoteToken):
		edge, remoteID = self.resolveRemoteEdge(remoteToken)
		localRoute = self.resolveLocalRoute(localToken)
		localRoute.setOutput(edge, remoteID)
		self.pendingRoutes[localToken].setResult(remoteToken)
		del self.pendingRoutes[localToken]
	
	def getMasterEdge(self):
		edge = SerialID.integerToBytes(0)
		self.routeEndpoints[edge] = Route(self.masterConnection)
		return edge
	
	def getLocalRoutingCode(self, route):
		self.routeCount += 1
		token = SerialID.integerToBytes(self.routeCount)
		self.routeEndpoints[token] = route
		return token
	
	def getFullRoutingCode(self, route):
		return route.getLocalCode()
	
	def openBusEdge(self, route):
		#TODO set a timeout
		self.routeCount += 1
		token = SerialID.integerToBytes(self.routeCount)
		self.routeEndpoints[token] = route
		self.pendingRoutes[token] = fut = Future()
		return token, fut
	
	def resolveLocalRoute(self, token):
		return self.routeEndpoints[token]
	
	def resolveRemoteEdge(self, token):
		return token, self.resolveLocalRoute(token).connection.__connection_id__
	
	@asynchronous
	def send(self, value):
		yield self.transport.put(value)
	
	def getBuffer(self, routingObject):
		return TransportBuffer(self, routingObject)
	
	def close(self):
		self.transport.put(None)
		await(self.loop)
	
	@asynchronous
	def activeLoop(self):
		""" Continuously pole the transport whilst the gateway remains open
		    this poling will be done in asychronous blocking mode so that it will
		    not 'spin' whilst no incoming data is present.
		"""
		while True:
			inObj = yield from self.transport.get()
			if inObj == None:
				break
			inStream = io.BytesIO(inObj)
			routingCode = SerialID.deserialize(inStream)
			route = self.routeEndpoints[routingCode]
			protocol = route.connection.protocol
			callLater(protocol.handleReceived, route, inStream)
	
