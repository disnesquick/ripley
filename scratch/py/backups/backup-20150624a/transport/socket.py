# System imports
import socket

# External imports
from unstuck import *

# Local imports
from ..serialize import *
from ..handshake import *
from .packet     import *

class SocketStreamServer(TransportServer):
	def __init__(self, listenAddress, connectionURI = None, backlog = 2):
		if isinstance(listenAddress, int):
			listenAddress = ("localhost",listenAddress)
		if connectionURI is None:
			connectionURI = ("tcp://%s:%d"%listenAddress).encode()
		super().__init__(connectionURI)
		
		self.listener = USocket()
		self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.listener.bind(listenAddress)
		self.listener.listen(backlog)
		
		self.worker = async(self.__acceptLoop())
		
	def connect(self, remoteAddress, shiboleth):
		return SocketStreamTransport.oneStepConnect(remoteAddress, shiboleth)
	
	@asynchronous
	def __acceptLoop(self):
		while True:
			socket = yield from self.listener.accept()
			async(self.__acceptClient(socket))
	
	@asynchronous
	def __acceptClient(self, socket):
			shiboleth = yield from socket.reader.readPacket4()
			
			if shiboleth != self.entryShiboleth:
				retries = 10
				while not shiboleth in self.acceptanceTokens and retries > 0:
					yield from sleep(0.1)
					retries -= 1
				if retries <= 0:
					yield from socket.close()
					return
				fut = self.acceptanceTokens.pop(shiboleth)
				
				transport = SocketStreamTransport(socket)
				fut.setResult(transport)
			
			elif self.entryShiboleth is not None:
				transport = SocketStreamTransport(socket)
				transport.awaitClient(self.entryConnection)


class SocketStreamTransport(PacketTransport):
	def __init__(self, socket):
		self.socket = socket
		super().__init__(socket.reader.readPacket4, socket.writer.writePacket4)
	
	@asynchronous
	def release(self):
		self.socket.reader.forceRelease(StreamClosed)
		yield from self.socket.writer.release()
		yield from self.worker
	
	@classmethod
	def oneStepConnect(cls, address, shiboleth):
		return await(cls._makeConnect(address, shiboleth))
	
	@classmethod
	def protocolConnect(cls, straddr, shiboleth):
		addr, port = straddr.split(":")
		port = int(port)
		return cls.oneStepConnect((addr,port), shiboleth)
	
	@asynchronous
	@classmethod
	def _makeConnect(cls, remoteAddress, shiboleth):
		socket = USocket()
		yield from socket.connect(remoteAddress)
		yield from socket.writer.writePacket4(shiboleth)
		return cls(socket)


OpenTransport.registerProtocol("tcp", SocketStreamTransport.protocolConnect)

