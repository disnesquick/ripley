
/* @declare bus_base
   *
   * @require connection
 */
var Bus, TimeoutError,
  __hasProp = {}.hasOwnProperty,
  __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };

TimeoutError = (function(_super) {
  __extends(TimeoutError, _super);

  function TimeoutError() {
    return TimeoutError.__super__.constructor.apply(this, arguments);
  }

  return TimeoutError;

})(Error);

Bus = (function() {

  /* A central organization object for Connections.
  	
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
   */
  function Bus(bus, connectionID) {
    var bound, i, _i;
    this.messageCount = -1;
    this.messageQueues = [];
    for (i = _i = 0; 0 <= mqLen ? _i <= mqLen : _i >= mqLen; i = 0 <= mqLen ? ++_i : --_i) {
      this.messageQueues.push({});
    }
    bound = this.messageQueuesTick.bind(this);
    this.messageQueueWatchdog = setInterval(bound, tickLen);
  }

  Bus.prototype.messageQueuesTick = function() {

    /* Single tick for the message queue timeout accounting.
    		
    		    Messages are timed out using a shift FIFO. Each tick moves those
    		    messages which have not yet been answered on, in this queue. When a
    		    messages reaches the end of this FIFO, the message is timed out,
    		    being `answered' with a TimeoutError exception.
     */
    var cbs, deadQueue, errorCB, _, _results;
    this.messageQueues.unshift({});
    deadQueue = this.messageQueues.pop();
    _results = [];
    for (_ in deadQueue) {
      cbs = deadQueue[_];
      errorCB = cbs[1];
      _results.push(errorCB(new TimeoutError()));
    }
    return _results;
  };

  Bus.prototype.waitForReply = function(successCallback, errorCallback, shiboleth) {

    /* Assigns callbacks and a check-value to a messageID.
    		
    		    This method assigns a messageID to a pair of callbacks. These
    		    are the `success' and `error' callbacks. When the outgoing call is
    		    replied to, the generated messageID will be used to match the
    		    response to these callbacks. In addition, a shiboleth is supplied.
    		    This is the outgoing Route and must match the incoming Route of the
    		    response, otherwise the response will be ignored. This is to prevent
    		    spoofing.
     */
    var messageID, subQueue;
    this.messageCount += 1;
    messageID = SerialID.integerToBytes(this.messageCount);
    subQueue = this.messageQueues[0];
    subQueue[messageID] = [successCallback, errorCallback, shiboleth];
    return messageID;
  };

  Bus.prototype.resolveMessageID = function(messageID, shiboleth) {

    /* Resolves a message ID to a a pair of callbacks.
    		
    		    Checks whether the message ID exists in the current map, to see if a
    		    message has indeed been sent to the remote end. If it has then
    		    remove the message callbacks from the queue and return them. This
    		    method also checks the shiboleth provided as an argument to the
    		    shiboleth registered to the message.
     */
    var subQueue, vals, _i, _len, _ref;
    _ref = this.messageQueues;
    for (_i = 0, _len = _ref.length; _i < _len; _i++) {
      subQueue = _ref[_i];
      if (messageID in subQueue) {
        vals = subQueue[messageID];
        if (vals[2] !== shiboleth) {
          throw new UnknownMessageIDError(messageID);
        }
        subQueue.pop(messageID);
        vals.pop();
        return vals;
      }
    }
    throw new UnknownMessageIDError(messageID);
  };

  Bus.prototype.getBootstrapConnection = function(transport) {

    /* Use a BootstrapTransport to create a Connection.
    		
    		    This method is used for a neonate Bus, which is currently unable
    		    to do anything, since it does not have a registered master service.
    		    A new Connection is created, connected to the remote Bus, which must
    		    offer a BusMasterService. This connection is then returned, fully
    		    connected, along with the instantiated BusMasterService.
     */
    var openRoute, ret, routeToken;
    openRoute = new OpenRoute();
    routeToken = openRoute.supplyTransport(transport);
    ret = (function(_this) {
      return function() {
        var connection, masterBusID;
        connection = null;
        masterBusID = null;
        return transport.bootstrap(routeToken).then(function(result) {
          var connectionID, masterID, route, routeCode, service;
          routeCode = result[0], connectionID = result[1], masterID = result[2], masterBusID = result[3];
          connection = new Connection(_this, connectionID);
          openRoute.supplyConnection(connection);
          openRoute.completeRoute(routeCode, masterID);
          route = openRoute.route;
          service = new BusMasterService(route);
          return service.getBusMaster(void 0);
        }).then(function(busMaster) {
          connection.addTransverseMap(busClientService.exposedTransverse);
          connection.addTransverseMap(basicErrorService.exposedTransverse);
          return [connection, busMaster, masterBusID];
        });
      };
    })(this);
    return ret();
  };

  Bus.prototype.connection = function() {

    /* Return a new Connection on this Bus.
    		
    		    This method creates a new Connection on the current Bus. A unique ID
    		    for the connection is requested from the BusMasterService for this
    		    Bus and is assigned to the new Connection.
     */
    var connectionID, neonate;
    connectionID = this.masterService.getNeonateID();
    neonate = new Connection(this, connectionID);
    neonate.addTransverseMap(basicErrorService.exposedTransverse);
    return neonate;
  };

  Bus.prototype.reportDestinationFailure = function(destination) {

    /* A destination is ms-behaving.
    		
    		    This method is used when a destination is shown to be behaving in a
    		    corrupted way. The only option is to cut the Route.
     */
    return destination.transport.unregisterRoute(destination);
  };

  return Bus;

})();
