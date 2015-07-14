# System imports
import os

# External imports
from unstuck import *

# Local imports
from ..handshake import OpenRoute
from ..bus       import SingleBus
from .base       import Transport

# Exports
__all__ = ["BootstrapTransport"]


class BootstrapTransport(Transport):
	def masterBootstrapIO(self, neonateID, masterToken, masterID):
		raise NotImplementedError
	
	def clientBootstrapIO(self, clientToken):
		raise NotImplementedError
	
	def awaitClient(self, connection):
		""" Instructs the transport to wait for 
		"""
		bus = connection.bus
		
		# Create a route to the master connection and supply this transport to
		# get the routing details.
		openMaster = OpenRoute(connection)
		masterToken = openMaster.supplyTransport(self)
		masterID = connection.connectionID
		
		# Create a connection ID for the bootstrapping neonate and then complete
		# the routing on both sides of the transport.
		neonateID = bus.masterService.getNeonateID()
		remoteToken = self.masterBootstrapIO(bus.busID, neonateID,
		                                     masterToken, masterID)
		openMaster.completeRoute(remoteToken, neonateID)
		
		# Register the transport on the bus as connecting to the remote bus
		bus.registerTransport(neonateID, self)
		
		# Finally launch the worker coroutine to process responses.
		self.engageTransport(neonateID)
	
	def bootstrap(self, clientToken):
		(clientID, masterToken,
		 masterID, remoteBusID) = self.clientBootstrapIO(clientToken)
		self.engageTransport(remoteBusID)
		return masterToken, clientID, masterID, remoteBusID
	
	@classmethod
	def bootstrapSingle(cls, *args):
		bus = SingleBus()
		transport = cls.oneStepConnect(*args)
		return bus.bootstrapOnTransport(transport)
