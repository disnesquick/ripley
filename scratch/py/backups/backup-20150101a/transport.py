import asyncio
import io
import websockets

class TransportClosed(Exception):
	pass

#TODO: 'side' negotiation protocol
class Transport:
	def blockUntilClosed(self):
		yield from self.recvCoro

	def setCallbacks(self, recvHook, errHook):
		self.recvCoro = asyncio.async(self.poleTransport(recvHook, errHook))
		self.recvCoro.add_done_callback(lambda fut: fut.result())

	@asyncio.coroutine
	def poleTransport(self, recvHook, errHook):
		""" Continuously pole the transport whilst the gateway remains open
		    this poling will be done in asychronous blocking mode so that it will
		    not 'spin' whilst no incoming data is present.
		"""
		self.isOpen = True
		def doneCallback(fut):
			try:
				fut.result()
			except TransportClosed:
				self.isOpen = False
				self.skip()

			except Exception as e:
				asyncio.get_event_loop().call_soon(errHook(e))
		while self.isOpen:
			serialPacket = (yield from self.recv())
			coro = recvHook(io.BytesIO(serialPacket))
			coro.add_done_callback(doneCallback)

	def beginWrite(self, messageType=b""):
		neonate = io.BytesIO()
		neonate.write(messageType)
		return neonate

	def commitWrite(self, message):
		yield from self.send(message.getvalue())


class LoopbackTransport(Transport):
	""" LoopbackTransport is used as a local-only test transport to allow
	    messages to be routed within the same thread. It uses asyncio
	    coroutines so the two endpoints must be using the same event loop
	"""
	@classmethod
	def getMatchedPair(cls):
		queue1 = asyncio.Queue()
		queue2 = asyncio.Queue()
		return cls(queue1, queue2, side=0),cls(queue2, queue1, side=1)
		
	def __init__(self, sendQueue, recvQueue, side=0):
		super().__init__()
		self.sendQueue = sendQueue
		self.recvQueue = recvQueue
		self.side = side

	def send(self, msg):
		#print("sending %s"%msg)
		yield from self.sendQueue.put(msg)

	def recv(self):
		data = yield from self.recvQueue.get()
		#print("%s have data %s"%(self,data))
		return data

	def skip(self):
		coro = self.recvQueue.put(b"")
		try:
			coro.send(None)
		except StopIteration:
			pass

	def hangUp(self):
		yield from self.recvQueue.put(b"")
		yield from self.sendQueue.put(b"")

	def portalNegotiation(self):
		return self.side


class WebsocketTransport(Transport):
	def __init__(self, connectedSocket):
		super().__init__()
		self.socket = connectedSocket
	
	def send(self, msg):
		#print("%s sending data %s"%(self,msg))
		yield from self.socket.send(msg)

	def skip(self):
		pass

	def recv(self):
		data = yield from self.socket.recv()
		#print("%s have data %s"%(self,data))
		return data

	def hangUp(self):
		yield from self.socket.close()
	
	def portalNegotiation(self):
		if isinstance(self.socket, websockets.client.WebSocketClientProtocol):
			return 0
		else:
			return 1
