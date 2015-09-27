# System imports
import io, os
import struct

# External imports
from unstuck.streams import *
from unstuck         import *

# Local imports
from .bootstrap  import BootstrapTransport
from ..serialize import *

# Exports
__all__ = ["PacketTransport"]


class PacketTransport(BootstrapTransport):
	""" The PacketTransport class is used to transport across Unstuck streams.
	
	    A PacketTransport is initialized with function readPacket and
	    writePacket representing the source and destination end-points
	    resectively. These can represent a connection across different machines
	    or between processes on the same machine. These two functions must be
	    coroutines.
	""" 
	def __init__(self, readPacket, writePacket):
		super().__init__()
		self.readPacket = readPacket
		self.writePacket = writePacket
	
	@asynchronous
	def release(self):
		raise(NotImplementedError)
	
	def masterBootstrapIO(self, busID, neonateID, masterToken, masterID):
		outStream = self.openBuffer(b"BOOTSTRP")
		ConnectionID.serialize(neonateID, outStream)
		RouteToken.serialize(masterToken, outStream)
		ConnectionID.serialize(masterID, outStream)
		BusID.serialize(busID, outStream)
		outStream.commitSync()
		
		inPacket = await(self.readPacket())
		inStream = io.BytesIO(inPacket)
		shiboleth = inStream.read(8)
		assert shiboleth == b"BOOTSTRP"
		
		clientToken = RouteToken.deserialize(inStream)
		return clientToken
	
	def clientBootstrapIO(self, clientToken):
		outStream = self.openBuffer(b"BOOTSTRP")
		RouteToken.serialize(clientToken, outStream)
		outStream.commitSync()
		
		inPacket = await(self.readPacket())
		inStream = io.BytesIO(inPacket)
		shiboleth = inStream.read(8)
		assert shiboleth == b"BOOTSTRP"
		
		connectionID = ConnectionID.deserialize(inStream)
		remoteToken = RouteToken.deserialize(inStream)
		masterID = ConnectionID.deserialize(inStream)
		remoteBusID = BusID.deserialize(inStream)
		return connectionID, remoteToken, masterID, remoteBusID
	
	def engageTransport(self, remoteBusID):
		self.remoteBusID = remoteBusID
		self.worker = async(self.ioLoop())
	
	def openBuffer(self, shiboleth):
		return PacketBuffer(self, shiboleth)
	
	def ioLoop(self):
		try:
			while True:
				inPacket = yield from self.readPacket()
				inStream = io.BytesIO(inPacket)
				routeCode = SerialID.deserialize(inStream)
				if routeCode in self.routeEndpoints:
					route = self.routeEndpoints[routeCode]
					callSoon(route.connection.handleReceived, route, inStream)
		except StreamClosed:
			pass
	
	def sendError(self, error):
		# TODO THIS IS A KLUDGE
		print(error)
		while True:pass


class PacketBuffer(io.BytesIO):
	def __init__(self, transport, shiboleth):
		super().__init__()
		self.transport = transport
		self.write(shiboleth)
	
	def commit(self):
		transport = self.transport
		val = self.getvalue()
		wrapFutureErrors(transport.sendError, async(transport.writePacket(val)))
	
	def commitSync(self):
		val = self.getvalue()
		return await(self.transport.writePacket(val))
