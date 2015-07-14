import websockets
import asyncio
from . import Transport, TransportClosed

class WebsocketTransport(Transport):
	def __init__(self, connectedSocket):
		super().__init__()
		self.socket = connectedSocket
	
	@asyncio.coroutine
	def send(self, msg):
		#print("%s sending data %s"%(self,msg))
		yield from self.socket.send(msg)

	@asyncio.coroutine
	def recv(self):
		data = yield from self.socket.recv()
		if data is None:
			raise(TransportClosed)
		#print("%s have data %s"%(self,data))
		return data

	@asyncio.coroutine
	def hangUp(self):
		yield from self.socket.close()
	
	def portalNegotiation(self):
		if isinstance(self.socket, websockets.client.WebSocketClientProtocol):
			return 1
		else:
			return 2
