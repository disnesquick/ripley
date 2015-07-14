import asyncio
import struct
from serialize import *
from errors import *
from shared import *
from transport import *

class ExposedCallable(PassByReference):
	""" This class is a simple wrapped that associates a python function func, with a
	    Ripley call interface iface for exposure across a route.
	"""
	def __init__(self, func, iface):
		self.func = func
		self.iface = iface

class ObjectBroker:
	def __init__(self, subBroker = None):
		self.locked = False
		self.objectToSharedID = {}
		self.sharedIDToObject = {}
		self.exposedTransverse = {}
		if subBroker is None:
			subBroker = defaultSubBroker
		self.subBroker = subBroker
		if subBroker is None:
			self.sharedThreshold = -1
			self.sharedCount = -1
		else:
			self.sharedThreshold = subBroker.sharedCount
			self.sharedCount = self.sharedThreshold
			subBroker.lock()

	def lock(self):
		""" Locks the broker against further changes
		"""
		self.locked = True

	def generateShareID(self):
		""" Generates an object ID in the form of a byte-string. Object IDs consist of the
		    gateway tag plus a unique code for the object itself. This allows objects to be
		    mapped to a particular end-point of the gateway.
		"""
		self.sharedCount += 1
		return self.sharedCount
	
	def transverseToReference(self, transverseID):
		subBroker = self
		while subBroker is not None:
			if transverseID in subBroker.exposedTransverse:
				# return the exposed object associated with the transverse identifier
				return subBroker.exposedTransverse[transverseID]
			subBroker = subBroker.subBroker
		# This gateway does not know about this transverse identifier
		raise (UnknownTransverseIDError(transverseID))

	def exposeTransverseObject(self, transverseID, obj):
		""" Exposes an object through a transverseID, will generate the object ID
		    if required.
		"""
		self.exposedTransverse[transverseID] = self.objectToReference(obj)

	def exposeCallImplementation(self, iface, func):
		""" Exposes a function call func that conforms to the interface iface
		"""
		uuid = iface.__transverse_id__
		self.exposeTransverseObject(uuid, ExposedCallable(func, iface))

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
	
	def objectToReference(self, obj):
		""" Obtains a reference identifier for the object. If the object has been shared
		    previously then the previous reference is returned, otherwise a reference is
		    generated and marked against the object.
		"""
		if obj in self.objectToSharedID:
			return self.objectToSharedID[obj]
		else:
			# search through the sub brokers and cache the object up-stream if it is found
			# for faster retrieval next time.
			subBroker = self.subBroker
			while subBroker is not None:
				if obj in subBroker.objectToSharedID:
					sharedID = subBroker.objectToSharedID[obj]
					self.objectToSharedID[obj] = sharedID
					return sharedID
				subBroker = subBroker.subBroker
		
		# Cannot add any more objects to a locked broker
		if self.locked:
			raise(Exception("Attempt to add an object to locked broker"))

		# This is a new object so generate the reference and store them
		shareID = self.generateShareID()
		binaryID = SerialID.integerToBytes(shareID)
		self.sharedIDToObject[shareID] = obj
		self.objectToSharedID[obj] = binaryID
		
		return binaryID

	def referenceToObject(self, shareID):
		""" Returns the object corresponding to the reference ID. Must be a local object.
		"""
		shareID = SerialID.bytesToInteger(shareID)
		while shareID <= self.sharedThreshold:
			self = self.subBroker
		return self.sharedIDToObject[shareID]


class Router(ObjectBroker):
	""" Route is an object that defines a point-to-point connection between
	    two end-points. It is responsible for handling:
	     1. Storage of incoming messages to the appropriate handlers.
	     2. Memory of outgoing messages so that the responses can be
	        routed to the calling function.
	     3. Exposure of transverse objects by mapping to an object ID.
	     4. Assignation of object IDs to shared local objects.
	"""
	def __init__(self, transport, subBroker = None):
		super().__init__(subBroker)
		self.endpointID = SerialID.integerToBytes(transport.portalNegotiation())
		self.messageCount = -1
		self.transport = transport
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

	def resolveTransverseID(self, transverseID):
		""" Resolves a transverse object identifier into the objectID of the associated
		    local object, if it has been exposed through this router).
		"""
		# return the exposed object associated with the transverse identifier
		return self.endpointID, self.transverseToReference(transverseID)

	def generateMessageID(self):
		""" Assigns a message number to an outgoing message based upon an active window
		    method. This is used to keep the numbers as low as possible to minimize
		    transmission length.
		    TODO: This doesn't actually work but the code is currently harmless
		"""
		self.messageCount += 1
		return SerialID.integerToBytes(self.messageCount)

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

	def referenceObject(self, obj):
		""" Marks an object as a shared object and stores it in the shared object
		    list for retrieval through an object reference.
		"""
		if isinstance(obj, ProxyObject):
			return obj.__shared_id__
		else:
			return self.endpointID, self.objectToReference(obj)

	def dereferenceObject(self, arg, typ, gateway = None):
		""" Converts an incoming object reference into a python object. Local objects will
		    be mapped to their local python object whereas remote objects will be wrapped
		    in an object proxy.
		"""
		endpointID, objectID = arg
		if endpointID == self.endpointID:
			obj = self.referenceToObject(objectID)
			if not isinstance(obj, typ):
				raise(ReferenceTypeMismatchError(type(obj), typ))
		elif gateway is not None:
			obj = typ.getProxyClass()(gateway, arg)
		else:
			raise(UnknownObjectIDError(arg))
		return obj

	def waitForReply(self, messageID, gateway, decoder):
		""" Sets up a future which will be activated when the response to
		    the outgoing message comes in.
		""" 
		waiter = asyncio.Future()
		
		def resolve(byteStream):
			# Handle the argument marshalling
			response = decoder(gateway, byteStream)
			waiter.set_result(response)

		self.responseWaitingQueue[messageID] = resolve, waiter.set_exception
		return waiter
	
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
		def doneCallback(fut):
			try:
				fut.result()
			except Exception as e:
				asyncio.get_event_loop().run_until_complete(errHook(e))

		try:
			while True:
				receivedStream = io.BytesIO((yield from self.transport.recv()))
				coro = asyncio.async(recvHook(receivedStream))
				coro.add_done_callback(doneCallback)
		except TransportClosed:
			pass
	
# Set-up all the default objects which all routers must support
defaultSubBroker = None
defaultSubBroker = ObjectBroker()
for iface, cls in errorList:
	defaultSubBroker.exposeObjectImplementation(iface, cls)

from gateway import Gateway
