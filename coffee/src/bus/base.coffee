### @declare bus_base
  #
  # @require connection
###

class TimeoutError extends Error


class Bus
	### A central organization object for Connections.
	
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
	###
	constructor : (bus, connectionID) ->
		# Message handling
		@messageCount = -1
		@messageQueues = []
		for i in [0..mqLen]
			@messageQueues.push({})
		
		# Message time-out
		bound = @messageQueuesTick.bind(this)
		@messageQueueWatchdog = setInterval(bound, tickLen)
	
	##
	# Code for handling outgoing message responses
	##
	
	messageQueuesTick : () ->
		### Single tick for the message queue timeout accounting.
		
		    Messages are timed out using a shift FIFO. Each tick moves those
		    messages which have not yet been answered on, in this queue. When a
		    messages reaches the end of this FIFO, the message is timed out,
		    being `answered' with a TimeoutError exception.
		###
		@messageQueues.unshift({})
		deadQueue = @messageQueues.pop()
		
		for _, cbs of deadQueue
			errorCB = cbs[1]
			errorCB(new TimeoutError())
	
	waitForReply : (successCallback, errorCallback, shiboleth) ->
		### Assigns callbacks and a check-value to a messageID.
		
		    This method assigns a messageID to a pair of callbacks. These
		    are the `success' and `error' callbacks. When the outgoing call is
		    replied to, the generated messageID will be used to match the
		    response to these callbacks. In addition, a shiboleth is supplied.
		    This is the outgoing Route and must match the incoming Route of the
		    response, otherwise the response will be ignored. This is to prevent
		    spoofing.
		###
		@messageCount += 1
		messageID = SerialID.integerToBytes(@messageCount)
		subQueue = @messageQueues[0]
		subQueue[messageID] = [successCallback, errorCallback, shiboleth]
		messageID
	
	resolveMessageID : (messageID, shiboleth) ->
		### Resolves a message ID to a a pair of callbacks.
		
		    Checks whether the message ID exists in the current map, to see if a
		    message has indeed been sent to the remote end. If it has then
		    remove the message callbacks from the queue and return them. This
		    method also checks the shiboleth provided as an argument to the
		    shiboleth registered to the message.
		###
		for subQueue in @messageQueues
			if messageID of subQueue
				vals = subQueue[messageID]
				if vals[2] != shiboleth
					# An apparent attempt at message spoofing.
					throw new UnknownMessageIDError(messageID)
				subQueue.pop(messageID)
				vals.pop() # Vals = resultCB, errorCB
				# Return the resolution callback and the exception callback
				return vals
		
		# send a general error to the other-side if this message was unknown
		throw new UnknownMessageIDError(messageID)
	
	##
	# Code for bootstrapping
	##
	
	getBootstrapConnection : (transport) ->
		### Use a BootstrapTransport to create a Connection.
		
		    This method is used for a neonate Bus, which is currently unable
		    to do anything, since it does not have a registered master service.
		    A new Connection is created, connected to the remote Bus, which must
		    offer a BusMasterService. This connection is then returned, fully
		    connected, along with the instantiated BusMasterService.
		
		    RETURNS A PROMISE
		###
		# Create a Route and connect it to the supplied transport
		openRoute = new OpenRoute()
		routeToken = openRoute.supplyTransport(transport)
		
		# Derive the tokens from the bootstrap protocol
		do =>
			connection = null
			masterBusID = null
			transport.bootstrap(routeToken)
			.then (result) =>
				[routeCode, connectionID, masterID, masterBusID] = result
				
				# Create the Connection and complete the Route on it
				connection = new Connection(this, connectionID)
				openRoute.supplyConnection(connection)
				openRoute.completeRoute(routeCode, masterID)
				route = openRoute.route
				
				# Get the BusMaster and register this connection as a BusClient
				service = new BusMasterService(route)
				service.getBusMaster(undefined)
			.then (busMaster) ->
				connection.addTransverseMap(busClientService.exposedTransverse)
				connection.addTransverseMap(basicErrorService.exposedTransverse)
				
				[connection, busMaster, masterBusID]
	
	connection : () ->
		### Return a new Connection on this Bus.
		
		    This method creates a new Connection on the current Bus. A unique ID
		    for the connection is requested from the BusMasterService for this
		    Bus and is assigned to the new Connection.
		###
		connectionID = @masterService.getNeonateID()
		neonate = new Connection(this, connectionID)
		neonate.addTransverseMap(basicErrorService.exposedTransverse)
		neonate
	
	reportDestinationFailure : (destination) ->
		### A destination is ms-behaving.
		
		    This method is used when a destination is shown to be behaving in a
		    corrupted way. The only option is to cut the Route.
		###
		destination.transport.unregisterRoute(destination)
