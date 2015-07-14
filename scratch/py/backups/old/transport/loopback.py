import asyncio
from . import Transport, TransportClosed

class LoopbackTransport(Transport):
	""" LoopbackTransport is used as a local-only test transport to allow
	    messages to be routed within the same thread. It uses asyncio
	    coroutines so the two endpoints must be using the same event loop
	"""
	@classmethod
	def getMatchedPair(cls):
		queue1 = asyncio.Queue()
		queue2 = asyncio.Queue()
		return cls(queue1, queue2, side=1),cls(queue2, queue1, side=2)
		
	def __init__(self, sendQueue, recvQueue, side=0):
		super().__init__()
		self.sendQueue = sendQueue
		self.recvQueue = recvQueue
		self.side = side

	@asyncio.coroutine
	def send(self, msg):
	#	print("sending %s"%msg)
		yield from self.sendQueue.put(msg)

	@asyncio.coroutine
	def recv(self):
		data = yield from self.recvQueue.get()
	#	print("%s have data %s"%(self,data))
		if data == b"":
			raise(TransportClosed)
		return data

	@asyncio.coroutine
	def hangUp(self):
		yield from self.recvQueue.put(b"")
		yield from self.sendQueue.put(b"")

	def portalNegotiation(self):
		return self.side

