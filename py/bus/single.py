# Local imports
from ..connection import Connection
from ..core_impl import OpenRoute, BusMasterService, busClientService
from .base import Bus

# Exports
__all__ = ["SingleBus"]

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
		(connection, busMaster,
		 remoteBusID            ) = self.getBootstrapConnection(transport)
		self.busMaster = busMaster
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
		routeToken = transport.getRoutingToken()
		
		# Derive the tokens from the bootstrap protocol
		(routeCode, connectionID,
		 masterID, masterBusID  ) = transport.bootstrap(routeToken)
		
		# Create the Connection and complete the Route on it
		connection = Connection(self, connectionID)
		openRoute = OpenRoute(connection)
		openRoute.bootstrap(transport, routeToken, routeCode, masterID)
		route = openRoute.route
		
		# Get the BusMaster and register this connection as a BusClient
		service = BusMasterService(route)
		busMaster = service.getBusMaster(None)
		connection.addTransverseMap(busClientService.exposedTransverse)
		#connection.addTransverseMap(basicErrorService.exposedTransverse)
		
		return connection, busMaster, masterBusID

