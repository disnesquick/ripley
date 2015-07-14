# System imports
import os

# Local imports
from ..serialize import *

# Exports
__all__ = ["Transport"]


class Transport:
	""" Base class for all bus-to-bus transport protocols.
	
	    A Transport provides the link between Routes. A Transport is defined
	    with an implicit source and destination Bus. These can be the same Bus,
	    although this concept should only be reified in the LoopbackBus. A
	    Transport can handle transfers between any number of Routes but only so
	    long as Route pairs lie on the implicit source/destination busses.
	    A transport takes care of the physical transfer of the binary stream of
	    a fully marshalled message from the source route to the destination
	    route. The Transport takes care of providing the Route objects with a
	    shiboleth, which may be unique to the Transport sub-class, which is then
	    encoded to identify the correct destination Route. A simple counter is
	    provided as a basic identifier but this may be over-ridden.
	"""
	def __init__(self):
		self.routeCount = -1
		self.routeEndpoints = {}

	def registerRoute(self, route):
		self.routeCount += 1
		token = SerialID.integerToBytes(self.routeCount)
		self.routeEndpoints[token] = route
		return token
	
	def unregisterRoute(self, route):
		del self.routeEndpoints[route.token]
	
	def engageTransport(self, remoteID):
		raise NotImplementedError
	
	def openBuffer(self, shiboleth):
		raise NotImplementedError
