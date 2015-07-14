### @declare bus_full
  #
  # @require bus_base
  # @require connection
###


class FullBus extends Bus
	### A FullBus is a Bus with multiple Transports and Connections.
	
	    The primary extension of the FullBus is the inclusion of a transport map
	    and the enabling of multiple Connections. The Transport map maps unique
	    per-Bus IDs to the appropriate Transport from this Bus. A FullBus
	    therefore is useful in a complicate graph of inter-connected processors.
	    A FullBus is also required to run a BusMasterService, as SimpleBusses
	    cannot.
	###
	constructor : (mqLen, tickLen) ->
		super(mqLen, tickLen)
		@transports = {}
		@transportCount = -1
	
	engageBus : (busID, noLoopback = false) ->
		### Activate the Bus with the specified BusID.
		
		    This method is called when a new bus is to be used. It has the
		    effect of assigning the ID to this bus and creating the Loopback,
		    unless this is actively blocked.
		###
		@busID = busID
		if not noLoopback
			loopback = LoopbackTransport()
			loopback.engageTransport(busID)
			@registerTransport(busID, loopback)
	
	registerTransport : (busID, transport) ->
		### Register a Transport as the link to a remote Bus.
		
		    This method informs the Bus that the provided Transport connects
		    this bus to the remote Bus identified by the BusID. The transport
		    is wrapped in a Promise for ease of use by resolveTransport which
		    must return a Promise.
		###
		@transports[busID] = Promise.resolve(transport)
	
	resolveTransport  : (busID) ->
		### Resolve an endpoint Bus to the appropriate Transport.
		
		    This function requests a Transport between this Bus and the remote
		    Bus identified by the provided BusID. If no Transport is currently
		    available then an attempt is made to connect a new Transport between
		    this Bus and the remote Bus, and the Transport is cached.
		
		    RETURNS A PROMISE
		###
		if not busID in @transports
			request = new OpenTransport()
			@masterService.requestConnection(request, busID)
			request.transportPromise.then((neonate) ->
				@registerTransport(busID, neonate)
				neonate.engageTransport(busID)
			)
		else
			@transports[busID]
	
	registerServer : (server, code) ->
		### Register an entry server with the BusMaster.
		
		    This is a convenience method to avoid using the masterService
		    directly. Simply passes TransportServer and URL for the server
		    through the the BusMasterService call.
		###
		if not code?
			code = server.connectionURI
		@masterService.registerServer(server, code)
