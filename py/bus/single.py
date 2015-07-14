# Local imports
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
