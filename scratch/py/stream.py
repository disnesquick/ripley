# System imports
import io, os
import struct

# External imports
from unstuck.streams import *
from unstuck         import *

# Local imports
from .bootstrap  import *
from ..serialize import *

# Exports
__all__ = ["StreamTransport"]


class StreamTransport(BootstrapTransport):
	""" The StreamTransport class is used to transport across Unstuck streams.
	
	    A StreamTransport is initialized with a ReadWrapper and a WriteWrapper,
	    representing the source and destination end-points resectively. These
	    can represent a connection across different machines or between
	    processes on the same machine.
	""" 
	def __init__(self, rStream, wStream):
		super().__init__()
		self.rStream = rStream
		self.wStream = wStream
	
	@asynchronous
	def release(self):
		self.rStream.forceRelease(StreamClosed)
		yield from self.wStream.release()
		yield from self.worker
	
	def masterBootstrapIO(self, busID, neonateID, masterToken, masterID):
		outStream = self.openBuffer(b"BOOTSTRP")
		ConnectionID.serialize(neonateID, outStream)
		RouteToken.serialize(masterToken, outStream)
		ConnectionID.serialize(masterID, outStream)
		BusID.serialize(busID, outStream)
		outStream.commitSync()
		
		inPacket = await(self.rStream.readPacket4())
		inStream = io.BytesIO(inPacket)
		shiboleth = inStream.read(8)
		assert shiboleth == b"BOOTSTRP"
		
		clientToken = RouteToken.deserialize(inStream)
		return clientToken
	
	def clientBootstrapIO(self, clientToken):
		outStream = self.openBuffer(b"BOOTSTRP")
		RouteToken.serialize(clientToken, outStream)
		outStream.commitSync()
		
		inPacket = await(self.rStream.readPacket4())
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
		return StreamBuffer(self, shiboleth)
	
	def ioLoop(self):
		try:
			while True:
				inPacket = yield from self.rStream.readPacket4()
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


class StreamBuffer(io.BytesIO):
	def __init__(self, transport, shiboleth):
		super().__init__()
		self.transport = transport
		self.write(shiboleth)
	
	def commit(self):
		val = self.getvalue()
		wrapFutureErrors(self.transport.sendError,
		                 async(self.transport.wStream.writePacket4(val)))
	
	def commitSync(self):
		val = self.getvalue()
		return await(self.transport.wStream.writePacket4(val))
