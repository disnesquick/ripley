# System imports
import io, os
import struct

# External imports
from unstuck.websockets import *
from unstuck         import *

# Local imports
from .packet import *
from ..serialize import *
from ..handshake import *


class WebsocketServer(TransportServer):
	def __init__(self, listenAddress, connectionURI = None, backlog = 2):
		if isinstance(listenAddress, int):
			listenAddress = ("localhost",listenAddress)
		if connectionURI is None:
			connectionURI = ("ws://%s:%d"%listenAddress).encode()
		super().__init__(connectionURI)
		
		self.listener = USocket.listener(listenAddress, backlog)
		self.worker = async(self.__acceptLoop())
	
	def connect(self, remoteAddress, shiboleth):
		return WebsocketTransport.oneStepConnect(remoteAddress, shiboleth)
	
	@asynchronous
	def __acceptLoop(self):
		while True:
			socket = yield from self.listener.accept()
			async(self.__acceptClient(socket))
	
	@asynchronous
	def __acceptClient(self, socket):
		yield from websockets.serverHandshake(socket)
		websocket = Websocket(socket)
		shiboleth = yield from websocket.recv()
		
		if shiboleth != self.entryShiboleth:
			retries = 10
			while not shiboleth in self.acceptanceTokens and retries > 0:
				yield from sleep(0.1)
				retries -= 1
			if retries <= 0:
				yield from websocket.close()
				return
			fut = self.acceptanceTokens.pop(shiboleth)
			
			transport = WebsocketTransport(websocket)
			fut.setResult(transport)
		
		elif self.entryShiboleth is not None:
			transport = WebsocketTransport(websocket)
			transport.awaitClient(self.entryConnection)


class WebsocketTransport(PacketTransport):
	def __init__(self, websocket):
		super().__init__(websocket.recv, websocket.send)
		self.websocket = websocket
	
	@asynchronous
	def release(self):
		yield from self.websocket.close()
		yield from self.worker
	
	def sendError(self, error):
		# TODO THIS IS A KLUDGE
		print(error)
		while True:pass
	
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
		yield from websockets.clientHandshake(socket,"%s:%s"%remoteAddress)
		websocket = Websocket(socket, False, True)
		yield from websocket.send(shiboleth)
		return cls(websocket)


OpenTransport.registerProtocol("ws", WebsocketTransport.protocolConnect)
