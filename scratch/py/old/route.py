from shared import *

__all__ = ["Route", "OpenRoute", "OpenRouteInterface"]

class Route:
	""" A Route object defines a one-directional path from one connection,
	    through the bus to a corresponding route (which points to this
	    connection) on a separate connection. This enables reply-paths to work.
	    The one exception to this rule is the route from any connection to the
	    bus master. This will always point to the same route, no matter the
	    source route, and that route does not have a destination and cannot be
	    used. Hence the master-routes can only be used for notifications using
	    callByTransverse.
	"""
	def __init__(self, connection):
		self.connection = connection
	
	def setOutput(self, transport, shiboleth, endID):
		""" Called by the bus object when it has a valid edge object to supply
		    to this route.  This edge is whatsoever object the bus requires to
		    handle routing to the destination route.  This function also
		    supplies the endpointID for the output edge, so that it can be
		    supplied to the connection. This will be used for setting the 
		    correct route on proxy objects when remote references are received.
		"""
		self.transport = transport
		self.shiboleth = shiboleth
		self.connection.proxyTokens[endID] = self
	
	def getOutputBuffer(self):
		""" Called by the protocol to get a writeable buffer, which, when
		    committed, will transfer the package to the correct destination for
		    this Route.
		"""
		return self.transport.openBuffer(self.shiboleth)


class OpenRouteInterface(TransverseObjectInterface):
	def supplyConnection(self, transportCode:BuswideID,
	                           remoteRoutingCode:RouteToken,
	                           remoteID:ConnectionID):
		pass
	
	def getLocalToken(self) -> RouteToken:
		pass
	
	def getConnectionID(self) -> ConnectionID:
		pass


@implements(OpenRouteInterface)
class OpenRoute:
	def __init__(self, bus, route, localToken = None):
		if route is None:
			raise(Exception())
		self.route = route
		self.bus = bus
		self.localToken = bus.getLocalRoutingCode(route)
	
	def supplyConnection(self, transportCode, remoteRoutingCode, remoteID):
		if self.route is None:
			raise(Exception("code has already been supplied"))
		route = self.route
		self.route = None
		transport = self.bus.resolveTransport(transportCode)
		route.setOutput(transport, remoteRoutingCode, remoteID)
	
	def getLocalToken(self):
		return self.localToken
	
	def getConnectionID(self):
		return self.route.connection.connectionID

