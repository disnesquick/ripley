
/* @declare bus_full
   *
   * @require bus_base
   * @require connection
 */
var FullBus,
  __hasProp = {}.hasOwnProperty,
  __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
  __indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

FullBus = (function(_super) {
  __extends(FullBus, _super);


  /* A FullBus is a Bus with multiple Transports and Connections.
  	
  	    The primary extension of the FullBus is the inclusion of a transport map
  	    and the enabling of multiple Connections. The Transport map maps unique
  	    per-Bus IDs to the appropriate Transport from this Bus. A FullBus
  	    therefore is useful in a complicate graph of inter-connected processors.
  	    A FullBus is also required to run a BusMasterService, as SimpleBusses
  	    cannot.
   */

  function FullBus(mqLen, tickLen) {
    FullBus.__super__.constructor.call(this, mqLen, tickLen);
    this.transports = {};
    this.transportCount = -1;
  }

  FullBus.prototype.engageBus = function(busID, noLoopback) {
    var loopback;
    if (noLoopback == null) {
      noLoopback = false;
    }

    /* Activate the Bus with the specified BusID.
    		
    		    This method is called when a new bus is to be used. It has the
    		    effect of assigning the ID to this bus and creating the Loopback,
    		    unless this is actively blocked.
     */
    this.busID = busID;
    if (!noLoopback) {
      loopback = LoopbackTransport();
      loopback.engageTransport(busID);
      return this.registerTransport(busID, loopback);
    }
  };

  FullBus.prototype.registerTransport = function(busID, transport) {

    /* Register a Transport as the link to a remote Bus.
    		
    		    This method informs the Bus that the provided Transport connects
    		    this bus to the remote Bus identified by the BusID. The transport
    		    is wrapped in a Promise for ease of use by resolveTransport which
    		    must return a Promise.
     */
    return this.transports[busID] = Promise.resolve(transport);
  };

  FullBus.prototype.resolveTransport = function(busID) {

    /* Resolve an endpoint Bus to the appropriate Transport.
    		
    		    This function requests a Transport between this Bus and the remote
    		    Bus identified by the provided BusID. If no Transport is currently
    		    available then an attempt is made to connect a new Transport between
    		    this Bus and the remote Bus, and the Transport is cached.
    		
    		    RETURNS A PROMISE
     */
    var request, _ref;
    if (_ref = !busID, __indexOf.call(this.transports, _ref) >= 0) {
      request = new OpenTransport();
      this.masterService.requestConnection(request, busID);
      return request.transportPromise.then(function(neonate) {
        this.registerTransport(busID, neonate);
        return neonate.engageTransport(busID);
      });
    } else {
      return this.transports[busID];
    }
  };

  FullBus.prototype.registerServer = function(server, code) {

    /* Register an entry server with the BusMaster.
    		
    		    This is a convenience method to avoid using the masterService
    		    directly. Simply passes TransportServer and URL for the server
    		    through the the BusMasterService call.
     */
    if (code == null) {
      code = server.connectionURI;
    }
    return this.masterService.registerServer(server, code);
  };

  return FullBus;

})(Bus);
