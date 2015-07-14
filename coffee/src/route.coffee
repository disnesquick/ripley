### @declare route
  #
  # @require share
###

class Route
	### A Route reifies a path to a Connection on a Bus.
	    
	    A Route object defines a one-directional path from one connection,
	    through the bus to a corresponding route (which points to this
	    connection) on a separate connection. This enables reply-paths to work.
	    Thus, when a Route is created, it must be during some process which
	    creates a corresponding Route on the other Bus.  A Route is therefore
	    always created via an OpenRoute object.
	###
	constructor : (transport) ->
		@transport = transport
		@token = transport.registerRoute(self)
		@lastRoute = self
	
	setDestination : (shiboleth, endID) ->
		### Supply details for remote end-point beyond the remote Bus.
		
		    When a Route is initialized, only the Transport is supplied, i.e.
		    The connection from source to destination Bus. However, a Route must
		    also connect a Connection on the source Bus to a Connection on the
		    destination Bus (i.e. provide routing beyond Busses, which is the
		    remit of the Transport object. This function provides the ID of the
		    end-point connection (for Reference reificiation) as well as a
		    serial shiboleth. When this shiboleth is prepended to a binary
		    stream, the rest of the stream will be routed to the destination
		    Connection by the remote Transport.
		###
		@shiboleth = shiboleth
		@connection.proxyTokens[endID] = this
		return # Null
	
	setOrigin : (connection) ->
		### Supply details for local end-point beyond the local Bus.
		
		    This is (obviously) the mirror function for setDestination. Whereas
		    the function provides the routing details for reaching a remote
		    Connection. This function simply provides the object for the actual
		    local object (Connection). Bonza.
		###
		@connection = connection
		return # Null
	
	getOutputBuffer : () ->
		### Called to get a writeable buffer on this Route.
		
		    The writeable buffer represents a data transfer to the endpoint of
		    this Route, which, when committed, will transfer the package to the
		    correct destination for this Route.
		###
		if @transport is None:
			throw new Error("Route was disconnected"))
		@transport.openBuffer(@shiboleth)
