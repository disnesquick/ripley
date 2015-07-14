from collections import deque

from unstuck import *

from connection import *
from bus_master import *
from errors import *


__all__ = ["FullBus", "SingleBus", "TimeoutError"]

class TimeoutError(Exception):
	pass

class Bus:
	""" A central organization object for Connections.
	
	    A Bus is one of the central organizational objects for a Ripley network.
	    A bus provides a connection point for any number of Connections. These
	    objects interact with each other via Routes, which connect two
	    Connection objects across each of their respective local Busses, through
	    a Transport object. Two busses are therefore connected via a Transport
	    object.
	    
	    The root Bus handles only a few operations. These are message accounting
	    i.e. the assignation of a unique ID to an outgoing message and the
	    assignation of the response with the same ID to the appropriate
	    listener and also bootstrapping a first Connection object over an
	    unattached transport (A transport which connects the physical components
	    of the two operating spaces of the two busses but not the actual busses
	    themselves).
	"""
	def __init__(self, *, mqLen = 5, tickLen = .5):
		# Message handling
		self.messageCount = -1
		self.messageQueues = deque(maxlen=mqLen)
		for i in range(mqLen):
			self.messageQueues.append(dict())
		
		# Message time-out
		self.messageQueueWatchdog = RecurringEvent(tickLen,
		                                           self.messageQueuesTick)
		self.messageQueueWatchdog.begin()
	
	##
	# Code for handling outgoing message responses
	##
	
	def messageQueuesTick(self):
		""" Single tick for the message queue timeout accounting.
		
		    Messages are timed out using a shift FIFO. Each tick moves those
		    messages which have not yet been answered on, in this queue. When a
		    messages reaches the end of this FIFO, the message is timed out,
		    being `answered' with a TimeoutError exception.
		"""
		deadQueue = self.messageQueues.pop()
		self.messageQueues.appendleft(dict())
		
		for _, vals in deadQueue.items():
			errorCB = vals[1]
			errorCB(TimeoutError)
	
	def waitForReply(self, successCallback, errorCallback, shiboleth):
		""" Assigns callbacks and a check-value to a messageID.
		
		    This method assigns a messageID to a pair of callbacks. These
		    are the `success' and `error' callbacks. When the outgoing call is
		    replied to, the generated messageID will be used to match the
		    response to these callbacks. In addition, a shiboleth is supplied.
		    This is the outgoing Route and must match the incoming Route of the
		    response, otherwise the response will be ignored. This is to prevent
		    spoofing.
		"""
		self.messageCount += 1
		messageID = SerialID.integerToBytes(self.messageCount)
		subQueue = self.messageQueues[0]
		subQueue[messageID] = successCallback, errorCallback, shiboleth
		return messageID
	
	def resolveMessageID(self, messageID, shiboleth):
		""" Resolves a message ID to a a pair of callbacks.
		
		    Checks whether the message ID exists in the current map, to see if a
		    message has indeed been sent to the remote end. If it has then
		    remove the message callbacks from the queue and return them. This
		    method also checks the shiboleth provided as an argument to the
		    shiboleth registered to the message.
		"""
		for subQueue in self.messageQueues:
			if messageID in subQueue:
				resultCB, errorCB, messageShiboleth = subQueue[messageID]
				if messageShiboleth != shiboleth:
					# An apparent attempt at message spoofing.
					raise(UnknownMessageIDError(messageID))
				subQueue.pop(messageID)
				# Return the resolution callback and the exception callback
				return resultCB, errorCB
		
		# send a general error to the other-side if this message was unknown
		raise(UnknownMessageIDError(messageID))
	
	##
	# Code for bootstrapping
	##
	
	def getBootstrapConnection(self, transport):
		""" Use a BootstrapTransport to create a Connection.
		
		    This method is used for a neonate Bus, which is currently unable
		    to do anything, since it does not have a registered master service.
		    A new Connection is created, connected to the remote Bus, which must
		    offer a BusMasterService. This connection is then returned, fully
		    connected, along with the instantiated BusMasterService.
		"""
		# Create a Route and connect it to the supplied transport
		openRoute = OpenRoute()
		routeToken = openRoute.supplyTransport(transport)
		
		# Derive the tokens from the bootstrap protocol
		(routeCode, connectionID,
		 masterID, masterBusID  ) = transport.bootstrap(routeToken)
		
		# Create the Connection and complete the Route on it
		connection = Connection(self, connectionID)
		openRoute.supplyConnection(connection)
		openRoute.completeRoute(routeCode, masterID)
		route = openRoute.route
		
		# Get the BusMaster and register this connection as a BusClient
		service = BusMasterService(route)
		busMaster = service.getBusMaster(None)
		connection.addTransverseMap(busClientService.exposedTransverse)
		connection.addTransverseMap(basicErrorService.exposedTransverse)
		
		return connection, busMaster, masterBusID
	
	def connection(self):
		""" Return a new Connection on this Bus.
		
		    This method creates a new Connection on the current Bus. A unique ID
		    for the connection is requested from the BusMasterService for this
		    Bus and is assigned to the new Connection.
		"""
		connectionID = self.masterService.getNeonateID()
		neonate = Connection(self, connectionID)
		neonate.addTransverseMap(basicErrorService.exposedTransverse)
		return neonate
	
	def reportDestinationFailure(self, destination):
		""" A destination is ms-behaving.
		
		    This method is used when a destination is shown to be behaving in a
		    corrupted way. The only option is to cut the Route.
		"""
		destination.transport.unregisterRoute(destination)


class SingleBus(Bus):
	""" A SingleBus is a Bus with one Transport only.
	
	    This class is designed for application that do not need the complexity
	    of the full routing capabilities of Ripley. To this end, this class only
	    uses a single transport, to a remote BusMaster and offerer of all the
	    Services to be used by this bus.
	
	    This Bus does not support a local BusMaster.
	"""
	def bootstrapOnTransport(self, transport):
		""" Attaches the Bus to its Transport and makes the sole Connection.
		
		    This is the only way to get a Connection for a SingleBus. It is
		    responsible for bootstrapping the Route, Connection and
		    MasterService over the BootstrapTransport. It then sets the
		    supplied transport as the Bus's only Transport, sets the master
		    and returns the Connection for Services to be discovered on.
		"""
		(connection, masterService,
		 remoteBusID              ) = self.getBootstrapConnection(transport)
		self.masterService = masterService
		self.onlyTransport = transport
		return connection
	
	def resolveTransport(self, busID):
		""" Tries to resolve the remote busID to this Bus's Transport.
		
		    Whereas a FullBus will use this method to map a busID to a Transport
		    between this bus and the one referenced by the busID, for a
		    SingleBus, this method only equates to checking that the remote
		    BusID matches that on the remote end of its sole Transport.
		"""
		otherID = self.onlyTransport.remoteBusID
		if busID != otherID:
			raise(KeyError("Remote bus was not the right bus. Saw [%s] but"
			               "it should be [%s]"%(busID, otherID)))
		return self.onlyTransport
	

class FullBus(Bus):
	""" A FullBus is a Bus with multiple Transports and Connections.
	
	    The primary extension of the FullBus is the inclusion of a transport map
	    and the enabling of multiple Connections. The Transport map maps unique
	    per-Bus IDs to the appropriate Transport from this Bus. A FullBus
	    therefore is useful in a complicate graph of inter-connected processors.
	    A FullBus is also required to run a BusMasterService, as SimpleBusses
	    cannot.
	"""
	def __init__(self, *, mqLen = 5, tickLen = .5):
		super().__init__(mqLen = mqLen, tickLen = tickLen)
		# Transport accounting
		self.transports = {}
		self.transportCount = -1
	
	def engageBus(self, busID, noLoopback = False):
		""" Activate the Bus with the specified BusID.
		
		    This method is called when a new bus is to be used. It has the
		    effect of assigning the ID to this bus and creating the Loopback,
		    unless this is actively blocked.
		"""
		self.busID = busID
		if not noLoopback:
			loopback = LoopbackTransport()
			loopback.engageTransport(busID)
			self.registerTransport(busID, loopback)
	
	def registerTransport(self, busID, transport):
		""" Register a Transport as the link to a remote Bus.
		
		    This method informs the Bus that the provided Transport connects
		    this bus to the remote Bus identified by the BusID.
		"""
		self.transports[busID] = transport
	
	def resolveTransport(self, busID):
		""" Resolve an endpoint Bus to the appropriate Transport.
		
		    This function requests a Transport between this Bus and the remote
		    Bus identified by the provided BusID. If no Transport is currently
		    available then an attempt is made to connect a new Transport between
		    this Bus and the remote Bus, and the Transport is cached.
		"""
		if not busID in self.transports:
			request = OpenTransport()
			self.masterService.requestConnection(request, busID)
			self.transports[busID] = neonate = await(request)
			neonate.engageTransport(busID)
		return self.transports[busID]
	
	def registerServer(self, server, code):
		""" Register an entry server with the BusMaster.
		
		    This is a convenience method to avoid using the masterService
		    directly. Simply passes TransportServer and URL for the server
		    through the the BusMasterService call.
		"""
		self.masterService.registerServer(server, code)
	
	def bootstrapOnTransport(self, transport):
		""" Connects a neonate Bus to a remote BusMaster through a Transport.
		
		    This method is used to connect a new FullBus into a broader network
		    of busses. The Transport (which must not be connected to any other
		    busses, although no more than one bus should be available anyway),
		    already physically connected to the remote entry server, is used
		    via the BootstrapTransport protocol to get a Connection, with
		    a MasterService registered on it, along with the remoteBusID of the
		    BusMaster bus. The connectionID of the new Connection will be the
		    BusID for this Bus.
		"""
		(connection, masterService,
		 remoteBusID              ) = self.getBootstrapConnection(transport)
		self.masterService = masterService
		self.engageBus(connection.connectionID)
		self.registerTransport(remoteBusID, transport)
		return connection
	
	def bootstrapOnLocalMaster(self, busMaster):
		""" Connects a neonate Bus directly to a local BusMaster.
		
		    This method is used to connect a seeding FullBus to a local
		    BusMaster. This should only be used on the very first BusMaster in a
		    network of Busses, as the BusMaster used will not be able to
		    communicate with other Busses before passing over a Connection.
		    In this procedure, the BusMasterService is registered as the local
		    BusMaster. In addition, a Connection is created on the BusMaster and
		    the BusMaster is shared as a service over this Connection.
		"""
		self.busMaster = self.masterService = busMaster
		connectionID = busMaster.getNeonateID()
		self.engageBus(connectionID)
		connection = Connection(self, connectionID)
		connection.addTransverseMap(busMasterService.exposedTransverse)
		return connection
	
from transport import *
