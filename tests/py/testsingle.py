from service import Service
from share import TransverseObjectInterface
from serialize import *
from bus import *
from bus_master import BusMaster
from connection import Connection
import logging
import os
from unstuck import *
from transport import SocketStreamServer
from transport.socket import *
#logging.basicConfig(level=logging.DEBUG)
class TestInterface(TransverseObjectInterface):
	def __constructor__(a:Int32):
		pass
	def echo(self, msg:UnicodeString) -> (UnicodeString, Int32):
		pass

@implements(TestInterface)
class Test:
	def __init__(self, a):
		self.a = a
	def echo(self, msg):
		self.a+=1
		return "%s:%d"%(msg,self.a), self.a


class EchoService(Service):
	Test = TestInterface


echoService = EchoService.implementation(
	Test = Test)



def process1():
	print("PROCESS 1", os.getpid())
	bus = FullBus()
	server = SocketStreamServer(bus, 1292)
	busMaster = BusMaster(bus)
	connection = bus.bootstrapOnLocalMaster(busMaster)
	server.entryServer(b"hello", connection)
	connection = bus.connection()
	echoService.offerOn(connection)
	await(sleep(20))
	#await(transport.release())

import time
	#await(transport.release())
def process3():
	print("PROCESS 3", os.getpid())
	await(sleep(0.1))
	client = SocketStreamTransport.bootstrapSingle(("",1292), b"hello")
	print(client)
	await(sleep(0.25))
	gateway = EchoService.on(client)
	print("EchoService")
	test = gateway.Test(5)
	test.echo("blarg")
	a = [test.echo.async("blarg") for i in range(100)]
	start = time.time()
	a = awaitAll(*a)
	print((time.time()-start)/100)
	print(a)

	


pid = os.fork()
import sys
if pid:
	process1()
	os.waitpid(pid,0)
else:
	forkDispatcher()
	process3()
	sys.exit()
