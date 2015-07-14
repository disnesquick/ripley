import io

from unstuck import *
from .base import *

__all__ = ["LoopbackTransport"]

class LoopbackTransport(Transport):
	def __init__(self):
		super().__init__()
	
	def engageTransport(self, remoteID):
		self.remoteBusID = remoteID
	
	def openBuffer(self, shiboleth):
		return LoopbackBuffer(self, shiboleth)
	
	def commitPacket(self, inStream):
		route = self.routeEndpoints[inStream.dc]
		callSoon(route.connection.handleReceived, route, inStream)


class LoopbackBuffer(io.BytesIO):
	def __init__(self, transport, shiboleth):
		super().__init__()
		self.dc = shiboleth
		self.transport = transport
	
	def commit(self):
		self.seek(0)
		self.transport.commitPacket(self)
