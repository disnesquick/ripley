# System imports
from collections import deque

# External imports
from unstuck import *

# Local imports
from ..bus_master import *
from ..errors     import *
from ..transport  import *
from ..connection import *
from .base        import *

__all__ = ["FullBus"]

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
			neonate = request.awaitTransport()
			self.registerTransport(busID, neonate)
			neonate.engageTransport(busID)
		return self.transports[busID]
	
	def registerServer(self, server, code = None):
		""" Register an entry server with the BusMaster.
		
		    This is a convenience method to avoid using the masterService
		    directly. Simply passes TransportServer and URL for the server
		    through the the BusMasterService call.
		"""
		if code is None:
			code = server.connectionURI
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
	
	def bootstrapOnURI(self, uri):
		""" Connects a neonate Bus to a remote BusMaster through a URI.
		
		    This method is used as bootstrapOnTransport. The difference between
		    the two is that this method derives a Transport from the URI first
		    and then connects through that Transport, sub-calling through
		    bootstrapOnTransport once the Transport is obtained.
		"""
		request = OpenTransport()
		request.connect(uri.encode(), b"hello-entry")
		neonate = request.awaitTransport()
		return self.bootstrapOnTransport(neonate)
	
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
