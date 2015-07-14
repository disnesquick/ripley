from serialize import *
from shared import *
from gateway import *
from router import *
from transport import *
import asyncio
import websockets
class Test(TransverseObjectInterface):
	def __constructor__(a:Int32):
		pass
	def echo(self, msg:UnicodeString) -> (UnicodeString, Int32):
		pass

@implements(Test)
class TestImplementation:
	def __init__(self, a):
		self.a = a
	def echo(self, msg):
		self.a+=1
		return "%s:%d"%(msg,self.a), self.a


class FilterAdd(FilterElement):
	def __constructor__(add:Int32):
		pass

@implements(FilterAdd)
class FilterAddImplementation:
	def __init__(self, add):
		self.add = add

	def transcode(self, inStream, outStream):
		coded = bytes([(i+self.add)%0x100 for i in inStream.read(0x8000)])
		outStream.write(coded)

def builder(sender, receiver):
	try:
		remoteReceive = yield from sender << FilterAdd.newRemote(-1)
		remoteReply = yield from sender << FilterAdd.newRemote(1)
		localSend = FilterAddImplementation(1)
		localReceive = FilterAddImplementation(-1)

		test = yield from sender << Test.newRemote(1)
		test = test
		test.gateway = test.gateway.sendFilter(localSend, remoteReceive)
		test.gateway = test.gateway.replyFilter(localReceive, remoteReply)
		b=3
		while b > 0:
			try:
				a = yield from test.echo("arg")		
				print(a)
			except SerializedError:
				pass
			b -= 1
			

	except Exception as e:
		yield from sender.router.close()
		yield from receiver.router.close()
		print("ERROR")
		raise(e)

def testLoopbackTransport():
	ob = ObjectBroker()
	ob.exposeObjectImplementation(Test, TestImplementation)
	ob.exposeObjectImplementation(FilterAdd, FilterAddImplementation)
	t1, t2 = LoopbackTransport.getMatchedPair()
	r1, r2 = Router(t1, ob), Router(t2, ob)
	sender = r1.defaultGateway
	receiver = r2.defaultGateway
	
	asyncio.get_event_loop().run_until_complete(builder(sender, receiver))
	print("finished")
	asyncio.get_event_loop().run_until_complete(r1.close())
	asyncio.get_event_loop().run_until_complete(r2.close())
	asyncio.get_event_loop().close()


def testWebsocketTransport():
	@asyncio.coroutine
	def serverRoutine(websocket, path):
		print("new connection")
		receiver = TransportGateway(enc, WebsocketTransport(websocket), debugMode = True)
		receiver.exposeObjectImplementation(TestImplementation)
		yield from asyncio.sleep(0.5)
		a = yield from  (receiver << Test.requestNew(1))
		print(a)
		b = yield from a.echo("asd")
		print(b)
		b = yield from a.echo("asd")
		print(b)
		b = yield from a.echo("asd")
		print(b)

		#yield from receiver.serverMode()
		print("connection closed")


	@asyncio.coroutine
	def clientRoutine():
		websocket = yield from websockets.connect('ws://localhost:8765/')
		return TransportGateway(enc, WebsocketTransport(websocket), debugMode = True)
		

	start_server = websockets.serve(serverRoutine, 'localhost', 8765)
	asyncio.get_event_loop().run_until_complete(start_server)
	asyncio.get_event_loop().run_forever()
	#sender = asyncio.get_event_loop().run_until_complete(clientRoutine())
	#gah = sender << TestInterface.requestNew(1)
	#print(gah)
	#while True:
	#	print(gah.echo("asd"))

	#asyncio.get_event_loop().close()

#testWebsocketTransport()
testLoopbackTransport()
