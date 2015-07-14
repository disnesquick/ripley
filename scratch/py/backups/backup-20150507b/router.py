import asyncio
import struct
from serialize import *
from errors import *
from shared import *
from transport import *

class ExposedCall:
	""" This class is a simple wrapped that associates a python function func, with a
	    Riple call interface iface for exposure across a route.
	"""
	def __init__(self, func, iface):
		self.func = func
		self.iface = iface


class Router:
	""" Route is an object that defines a point-to-point connection between
	    two end-points. It is responsible for handling:
	     1. Storage of incoming messages to the appropriate handlers.
	     2. Memory of outgoing messages so that the responses can be
	        routed to the calling function.
	     3. Exposure of transverse objects by mapping to an object ID.
	     4. Assignation of object IDs to shared local objects.
	"""
	def __init__(self, transport, messageNumberBuffer = 200):
		self.endpointID = transport.portalNegotiation()
		self.sharedCount = -1
		self.messageCount = -1
		self.transport = transport
		self.objectToSharedID = {}
		self.sharedIDToObject = {}
		self.exposedTransverse = {}
		self.cachedTransverse = {}
		self.responseWaitingQueue = {}
		self.defaultGateway = Gateway(self)
		self.listenTask = self.defaultGateway.activateListener()

	@asyncio.coroutine
	def close(self):
		""" Closes the route and hangs up on the transport to let the other end know
		"""
		yield from self.transport.hangUp()
		yield from self.listenTask
	
	def generateMessageID(self):
		""" Assigns a message number to an outgoing message based upon an active window
		    method. This is used to keep the numbers as low as possible to minimize
		    transmission length.
		    TODO: This doesn't actually work but the code is currently harmless
		"""
		self.messageCount += 1
		return SerialID.integersToBytes(self.messageCount)

	def resolveMessageID(self, messageID):
		""" Checks whether the message ID exists in the current map, to see if a
		    message has indeed been sent to the remote end. If it has then update
		    the messageWindowLow if appropriate and return the response details.
		"""
		# Ensure that the message is a response to a message from this gateway
		if not messageID in self.responseWaitingQueue:
			# send a general error to the other-side if this message was unknown
			raise(UnknownMessageIDError(messageID))

		# Return the resolution callback and the exception callback
		return self.responseWaitingQueue.pop(messageID)

	def waitForReply(self, messageID, decoder):
		""" Sets up a future which will be activated when the response to
		    the outgoing message comes in.
		""" 
		waiter = asyncio.Future()
		
		def resolve(byteStream):
			# Handle the argument marshalling
			response = decoder(byteStream)
			waiter.set_result(response)

		self.responseWaitingQueue[messageID] = resolve, waiter.set_exception
		return waiter

	def generateShareID(self):
		""" Generates an object ID in the form of a byte-string. Object IDs consist of the
		    gateway tag plus a unique code for the object itself. This allows objects to be
		    mapped to a particular end-point of the gateway.
		"""
		self.sharedCount += 1
		return SerialID.integersToBytes(self.endpointID, self.sharedCount)
	
	def referenceObject(self, obj):
		""" Marks an object as a shared object and stores it in the shared object
		    list for retrieval through an object reference.
		"""
		if isinstance(obj, ProxyObject):
			return obj.__shared_id__
		if obj in self.objectToSharedID:
			return self.objectToSharedID[obj]
		shareID = self.generateShareID()
		self.sharedIDToObject[shareID] = obj
		self.objectToSharedID[obj] = shareID
		return shareID

	def dereferenceObject(self, arg, typ, gateway = None):
		""" Converts an incoming object reference into a python object. Local objects will
		    be mapped to their local python object whereas remote objects will be wrapped
		    in an object proxy.
		"""
		if arg in self.sharedIDToObject:
			arg = self.sharedIDToObject[arg]
			if not issubclass(type(arg), typ):
				raise(TypeError("%s was not of type %s as specified in the interface"%(arg, typ)))
		elif gateway is not None:
			arg = typ.getProxyClass()(gateway, arg)
		else:
			raise(UnknownObjectIDError(arg))
		return arg
	
	def cacheTransverse(self, transverseID, objectID):
		""" caches a resolved transverse ID / object ID pair so that future resolutions
		    do not have to go down the wire.
		""" 
		self.cachedTransverse[transverseID] = objectID

	def getCachedTransverse(self, transverseID):
		""" tries to retrieve an object ID from the previously cached transverse ID. If
		    that object had not been cached then raises a KeyError
		"""
		return self.cachedTransverse[transverseID]

	def resolveTransverseID(self, transverseID):
		""" Resolves a transverse object identifier into the objectID of the associated
		    local object, if it has been exposed through this router).
		"""
		if not transverseID in self.exposedTransverse:
			# This gateway does not know about this transverse identifier
			raise (UnknownTransverseIDError(transverseID))
		else:
			# return the exposed object associated with the transverse identifier
			return self.exposedTransverse[transverseID]

	def exposeCallImplementation(self, iface, func):
		""" Exposes a function call func that conforms to the interface iface
		"""
		uuid = iface.__transverse_id__
		self.exposedTransverse[uuid] = self.referenceObject(ExposedCall(func, iface))
	
	def exposeObjectImplementation(self, iface, cls):
		""" Exposes a python object that has been marked as an implementation of an object
		    to the other side(s) of the transport. If the interface is marked as
		    non-constructable, then no constructor method will be made available.
		"""
		for name, member in iface.__iface_members__.items():
			# If the object has a constructor then expose the object class itself 
			if name == "__constructor__":
				call = cls
			else:	
				call = getattr(cls,name)
			self.exposeCallImplementation(member, call)

	def getBuffer(self):
		""" returns a buffer to write an outgoing packet into.
		"""
		return self.transport.startWrite()

	@asyncio.coroutine
	def flushBuffer(self, buf):
		""" Commits the write of a send buffer to the wire.
		"""
		yield from self.transport.commitWrite(buf)

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
				self.transport.skip()
			except Exception as e:
				asyncio.get_event_loop().call_soon(errHook(e))

		while self.isOpen:
			receivedStream = io.BytesIO((yield from self.transport.recv()))
			coro = asyncio.async(recvHook(receivedStream))
			coro.add_done_callback(doneCallback)

from gateway import Gateway
