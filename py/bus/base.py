# System imports
from collections import deque

# External imports
from unstuck import *

# Local imports
from ..serialize import *
#from ..errors import *

# Exports
__all__ = ["TimeoutError", "Bus"]

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
		
		for _, cbs in deadQueue.items():
			errorCB = cbs[1]
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
	# Error handling
	##
	
	def reportDestinationFailure(self, destination):
		""" A destination is misbehaving.
		
		    This method is used when a destination is shown to be behaving in a
		    corrupted way. The only option is to cut the Route.
		"""
		destination.transport.unregisterRoute(destination)
	
	def handleLocalException(self, destination, err):
		print(err)
		raise err
