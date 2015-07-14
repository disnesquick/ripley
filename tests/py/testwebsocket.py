import logging
import os

from unstuck import *

from ripley import *
from ripley.bus import *
from ripley.transport import *

import test_iface
from test_iface import EchoService


@implements(test_iface.Test)
class Test:
	def __init__(self, a):
		self.a = a
	def echo(self, msg):
		self.a+=1
		return "%s:%d"%(msg,self.a), self.a


echoService = EchoService.implementation(
	Test)



def process1():
	print("PROCESS 1", os.getpid())
	bus = FullBus()
	server = WebsocketServer(1292)
	busMaster = BusMaster(bus)
	connection = bus.bootstrapOnLocalMaster(busMaster)
	server.entryServer(connection)
	await(sleep(20))
	#await(transport.release())

import time
def process2():
	print("PROCESS 2", os.getpid())
	bus = FullBus()
	server = WebsocketServer(1293)
	await(sleep(0.1))
	connection = bus.bootstrapOnURI("ws://localhost:1292")
	bus.registerServer(server)
	echoService.offerOn(connection)
	print("SERVER DONE")

	await(sleep(20))


	#await(transport.release())
def process3():
	print("PROCESS 3", os.getpid())
	bus = FullBus()
	await(sleep(0.1))
	bus.bootstrapOnURI("ws://localhost:1292")
	client = bus.connection()
	await(sleep(0.25))
	gateway = EchoService.on(client)
	test = gateway.Test(5)
	test.echo("as")
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
	pid = os.fork()
	forkDispatcher()
	if pid:
		process2()
		os.waitpid(pid,0)
	else:
		process3()
		sys.exit()
