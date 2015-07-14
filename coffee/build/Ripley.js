
/* @declare headers
 */
var headers;

headers = {
  HEADER_HUP: "\x00",
  HEADER_RESOLVE: "\x11",
  HEADER_NOTIFY: "\x12",
  HEADER_EVAL: "\x13",
  HEADER_NOTIFY_TRANS: "\x14",
  HEADER_EVAL_TRANS: "\x15",
  HEADER_REPLY: "\x16",
  HEADER_MESSAGE_ERROR: "\x17",
  HEADER_GENERAL_ERROR: "\x18",
  HEADER_TIME: "\x19",
  HEADER_FILTER_IN: "\x1A",
  HEADER_FILTER_OUT: "\x1B",
  HEADER_FILTER_ERR: "\x1C",
  HEADER_DEREF: "\x1D"
};


/* @declare connection
   *
   * @require headers
 */
var Connection;

Connection = (function() {
  function Connection(bus, connectionID) {
    this.objectToObjectID = {};
    this.objectIDToObject = {};
    this.sharedCount = -1;
    this.services = [];
    this.proxyTokens = {};
    this.bus = bus;
    this.connectionID = connectionID;
    this.cachedTransverse = {};
  }

  Connection.prototype.generateObjectID = function() {

    /* Generates an object ID in the form of a SerialID.
    		
    		    Referencess are transfered in the form of a connection-specific
    		    unique identifier plus an identifier for the connection itself.
    		    However, this connectionID is handled elsewhere.
     */
    this.objectCount += 1;
    return SerialID.integerToBytes(this.objectCount);
  };

  Connection.prototype.objectToReference = function(obj) {

    /* Obtains a reference identifier for an object.
    		
    		    If the object has been shared previously then the previous reference
    		    is returned, otherwise a reference is generated and marked against
    		    the object.  The connection ID is added for local objects to create
    		    a complete reference.
     */
    var objectID;
    if (obj(isinstance(ProxyObject))) {
      return obj.reference;
    } else if (obj in this.objectToObjectID) {
      objectID = this.objectToObjectID[obj];
      return [this.connectionID, objectID];
    } else {
      objectID = this.generateObjectID();
      this.objectIDToObject[objectID] = obj;
      this.objectToObjectID[obj] = objectID;
      return [this.connectionID, objectID];
    }
  };

  Connection.prototype.referenceToObject = function(reference, typ) {

    /* Maps an incoming object reference to a python object.
    		
    		    Local objects will be mapped to their local python object whereas
    		    remote objects will be wrapped in an object proxy.
     */
    var connectionID, destination, err, obj, objectID;
    connectionID = reference[0], objectID = reference[1];
    if (connectionID === this.connectionID) {
      if (!(objectID in this.objectIDToObject)) {
        throw new UnknownObjectIDError(objectID);
      }
      obj = this.objectIDToObject[objectID];
      if (!(obj(isinstance(typ)))) {
        throw new ReferenceTypeMismatchError(obj, typ);
      }
    } else {
      try {
        destination = this.proxyTokens[connectionID];
      } catch (_error) {
        err = _error;
        throw new RouteNotFound(this.connectionID, connectionID, reference, typ);
      }
      obj = new (typ.getProxyClass())(destination, reference);
    }
    return obj;
  };

  Connection.prototype.serializeObjects = function(objs, objTypes, outStream) {

    /* Serializes a list of objects.
    		
    		    The list of objects `objs' is serialized according to the types in
    		    the congruent list objTypes and written directly to outStream in
    		    binary form.
     */
    var idx, obj, _i, _len;
    for (idx = _i = 0, _len = objs.length; _i < _len; idx = ++_i) {
      obj = objs[idx];
      this.serializeObject(obj, typ[idx], outStream);
    }
  };

  Connection.prototype.serializeObject = function(obj, typ, outStream) {

    /* Serializes a single object.
    		
    		    The object `obj' is serialized according to the type `typ' and
    		    written to outStream in binary form. Objects can be PassByValue
    		    types, which will be directly serialized, or they can be local
    		    objects, in which case they will be assigned a suitable reference
    		    and that will be serialized.
     */
    var ref;
    if (typ(isinstance(PassByValue))) {
      if (typ(isinstance(ComplexPassByValue))) {
        typ.serialize(obj, this, outStream);
      } else {
        typ.serialize(obj, outStream);
      }
    } else {
      ref = this.objectToReference(obj);
      Reference.serialize(ref, outStream);
    }
  };

  Connection.prototype.deserializeObjects = function(objTypes, inStream) {

    /* Deserializes a list of objects.
    		
    		    A list of objects is extracted from the binary inStream according
    		    to the list of types `objTypes'.
     */
    var typ, _i, _len, _results;
    _results = [];
    for (_i = 0, _len = objTypes.length; _i < _len; _i++) {
      typ = objTypes[_i];
      _results.push(this.deserializeObject(typ, inStream));
    }
    return _results;
  };

  Connection.prototype.deserializeObject = function(typ, inStream) {

    /* Deserializes a single object from inStream.
    		
    		    According to the type typ, PassByValue objects are directly
    		    deserialized as they are serialized. For other kinds of objects a
    		    reference is deserialized and this is used to retrieve the object or
    		    create the appropriate proxy.
     */
    var ref;
    if (typ(isinstance(PassByValue))) {
      if (typ(isinstance(ComplexPassByValue))) {
        return typ.deserialize(this, inStream);
      } else {
        return typ.deserialize(inStream);
      }
    } else {
      ref = Reference.deserialize(inStream);
      return this.referenceToObject(ref, typ);
    }
  };

  Connection.prototype.addTransverseMap = function(transverseMap) {

    /* Adds a dictionary of transverse mappings to the Connection.
    		
    		    This method is usually applied when a ServiceImplementatiob object
    		    is offered on a Connection. The list of TransverseID -> Object
    		    mappings is added to this Connection so that future transverse
    		    resolutions will return the objects in question (or rather, the
    		    references to them).
     */
    this.transverseMaps.append(transverseMap);
  };

  Connection.prototype.transverseIDToReference = function(transverseID) {

    /* Maps a TransverseID to a Reference to the appropriate object.
    		
    		    Looks through the handled transvese maps to find the object
    		    corresponding to the TransverseID supplied and then maps the object
    		    to a Reference, for transmission over the wire.
     */
    var obj, transverseMap;
    for (transverseMap in this.transverseMaps) {
      if (transverseID in transverseMap) {
        obj = transverseMap[transverseID];
        return this.objectToReference(obj);
      }
    }
    throw new UnknownTransverseIDError(transverseID);
  };

  Connection.prototype.handleReceived = function(origin, inStream) {

    /* Processes the current waiting packet from inStream.
    		
    		    This procedure retrieves a message packet from inStream and acts
    		    according to the header byte received (the first byte read) to pass
    		    further processing to the appropriate subprocedure.
     */
    var header;
    header = inStream.read(1);
    if (header === headers.HEADER_RESOLVE) {
      this.receiveResolve(origin, inStream);
    } else if (header === headers.HEADER_NOTIFY) {
      this.receiveNotify(origin, inStream);
    } else if (header === headers.HEADER_EVAL) {
      this.receiveEval(origin, inStream);
    } else if (header === headers.HEADER_REPLY) {
      this.receiveReply(origin, inStream);
    } else if (header === headers.HEADER_MESSAGE_ERROR) {
      this.receiveMessageError(origin, inStream);
    } else if (header === headers.HEADER_GENERAL_ERROR) {
      this.receiveGeneralError(origin, inStream);
    } else if (header === headers.HEADER_FILTER_IN) {
      this.modifyIOFilterInput(origin, inStream);
    } else if (header === headers.HEADER_FILTER_OUT) {
      this.modifyIOFilterOutput(origin, inStream);
    } else {
      throw new DecodingError("Unrecognized header %s" % header);
    }
  };

  Connection.prototype.receiveResolve = function(origin, inStream) {

    /* Process a resolution request.
    		
    		    A resolution request consists of a message ID and a transverse ID.
    		    The transverse ID is mapped to the resident shared object ID if it
    		    is present, otherwise an error is sent.
     */
    var messageID, outStream, reference, te, transverseID;
    messageID = MessageID.deserialize(inStream);
    try {
      transverseID = TransverseID.deserialize(inStream);
      reference = this.transverseIDToReference(transverseID);
      outStream = origin.getOutputBuffer();
      outStream.write(headers.HEADER_REPLY);
      MessageID.serialize(messageID, outStream);
      Reference.serialize(reference, outStream);
      outStream.commit();
    } catch (_error) {
      te = _error;
      this.handleIncomingMessageError(origin, messageID, te);
    }
  };

  Connection.prototype.receiveNotify = function(origin, inStream) {

    /* Process a notification.
    		
    		    A notification is an  evaluation for which there is no return data.
    		    The request consists of a message ID and an object ID (the object
    		    must be local and a function/callable), followed by the serialized
    		    arguments for that function call.
     */
    var call;
    call = this.deserializeObject(ExposedCallable, inStream);
    call.handleNotification(this, inStream);
  };

  Connection.prototype.receiveEval = function(origin, inStream) {

    /* Process an evaluation request.
    		
    		    An evaluation request consists of a messageID and an objectID (the
    		    object must be local and a function/callable), followed by the
    		    serialized arguments for that object.
     */
    var call, messageID, outStream, te;
    messageID = MessageID.deserialize(inStream);
    try {
      call = this.deserializeObject(ExposedCallable, inStream);
      outStream = origin.getOutputBuffer();
      outStream.write(headers.HEADER_REPLY);
      MessageID.serialize(messageID, outStream);
      call.handleEval(this, inStream, outStream);
      outStream.commit();
    } catch (_error) {
      te = _error;
      this.handleIncomingMessageError(origin, messageID, te);
    }
  };

  Connection.prototype.receiveReply = function(origin, inStream) {

    /* Process a response to an evaluation or resolution request.
    		
    		    A reply notification consists of the message ID of the original
    		    message followed by serialized arguments for the response
    		    marshalling code.
     */
    var doneCall, messageID, _, _ref;
    messageID = MessageID.deserialize(inStream);
    _ref = this.bus.resolveMessageID(messageID, origin.lastRoute), doneCall = _ref[0], _ = _ref[1];
    doneCall(inStream);
  };

  def({
    receiveMessageError: function(origin, inStream) {

      /* Process an error response to a function evaluation.
      		
      		    An error is a hybrid of a reply and a notification. It consists of
      		    the message ID of the original message followed by an object ID for
      		    the exception object.
       */
      var error, exceptionObject, messageID, obj, transverseID, _, _ref;
      messageID = MessageID.deserialize(inStream);
      _ref = self.bus.resolveMessageID(messageID, origin.lastRoute), _ = _ref[0], error = _ref[1];
      transverseID = TransverseID.deserialize(inStream);
      try {
        obj = this.transverseIDToObject(transverseID);
        exceptionObject = obj.handleFetch(this, inStream);
        return error(exceptionObject);
      } catch (_error) {
        return error(new ErrorUnsupported(transverseID));
      }
    }
  });

  Connection.prototype.receiveGeneralError = function(origin, inStream) {

    /* Process an error received as a general failure.
    		
    		    An error is a hybrid of a reply and a notification. It consists of
    		    an object ID for the error function to call.
     */
    var exceptionObject, obj, transverseID;
    transverseID = TransverseID.deserialize(inStream);
    try {
      obj = this.transverseIDToObject(transverseID);
      exceptionObject = obj.handleFetch(this, inStream);
      error(exceptionObject);
    } catch (_error) {
      error(new ErrorUnsupported(transverseID));
    }
    return this.bus.handleGeneralError(origin, exceptionObject);
  };

  Connection.prototype.modifyIOFilterInput = function(origin, inStream) {

    /* Process the application of a filter to the incoming stream.
    		
    		    Remote end-point requests that a filter be applied to the incoming
    		    data.  This required that the correct filter object be extracted
    		    from the local shared object cache and then applied to the stream.
     */
    var filterElement, filteredStream;
    filterElement = this.deserializeObject(FilterElement, inStream);
    filteredStream = new StringIO();
    filterElement.transcode(inStream, filteredStream);
    filteredStream.seek(0);
    this.handleReceived(origin, filteredStream);
  };

  Connection.prototype.modifyIOFilterOutput = function(origin, inStream) {

    /* Process the addition of a filter on the response path.
    		
    		    Remote end-point requests that a filter be applied to the response
    		    to the incoming message. This requires that processing be shifted to
    		    a new gateway which has the appropriate filter pair in place.
     */
    var filterElementLocal, filterElementRemoteRef, subOrigin;
    filterElementLocal = this.deserializeObject(FilterElement, inStream);
    filterElementRemoteRef = Reference.deserialize(inStream);
    subOrigin = FilteredResponseRoute(origin, filterElementLocal, filterElementRemoteRef);
    this.handleReceived(subOrigin, inStream);
  };

  Connection.prototype.transceiveResolve = function(destination, transverseID) {

    /* Request the remote object ID corresponding to a transverse ID.
    		
    		    Takes a transverse descriptor and gets the appropriate shared
    		    object ID from the remote end of the connection. Message is sent out
    		    as a resolve request followed by a message ID and a transverse ID.
    		    Return is expected as a shared object ID.
     */
    return new Promise(function(result, error) {
      var cacheID, messageID, outStream, reply;
      cacheID = [destination.transport.remoteBusID, transverseID];
      if (cacheID in this.cachedTransverse) {
        return result(this.cachedTransverse[cacheID]);
      } else {
        reply = function(inStream) {
          var e, resolved;
          try {
            resolved = Reference.deserialize(inStream);
            this.cachedTransverse[cacheID] = resolved;
            return result(resolved);
          } catch (_error) {
            e = _error;
            return error(e);
          }
        };
        messageID = this.bus.waitForReply(reply, fut.setError, destination.lastRoute);
        outStream = destination.getOutputBuffer();
        outStream.write(headers.HEADER_RESOLVE);
        MessageID.serialize(messageID, outStream);
        TransverseID.serialize(transverseID, outStream);
        return outStream.commit();
      }
    });
  };

  Connection.prototype.transmitNotify = function(destination, callID) {

    /* Call a remote function without any response.
    		
    		    This function prepares an output stream connected to the destination
    		    Route provided. The message type will be tagged as a notification so
    		    no reply is expected.
     */
    var outStream;
    outStream = destination.getOutputBuffer();
    outStream.write(headers.HEADER_NOTIFY);
    Reference.serialize(callID, outStream);
    return outStream;
  };

  Connection.prototype.transceiveEval = function(destination, callID) {

    /* Call a remote function and retrieve the reply.
    		
    		    transceiveEval is responsible for sending out the EVAL message and
    		    then waiting for the response from the server.
     */
    var fut, outStream;
    outStream = destination.getOutputBuffer();
    fut = new Promise(function(result, error) {
      var messageID;
      messageID = this.bus.waitForReply(result, error, destination.lastRoute);
      outStream.write(headers.HEADER_EVAL);
      MessageID.serialize(messageID, outStream);
      return Reference.serialize(callID, outStream);
    });
    return [outStream, fut];
  };

  Connection.prototype.transmitMessageError = function(destination, messageID, error) {

    /* Transmit an exception to a destination as a message response.
    		
    		    This method is used to serialize a TransverseException as a response
    		    to a failed evaluation or resolution request.
     */
    var outStream;
    outStream = destination.getOutputBuffer();
    outStream.write(headers.HEADER_MESSAGE_ERROR);
    MessageID.serialize(messageID, outStream);
    error.serializeConstructor(this, outStream);
    return outStream.commit();
  };

  Connection.prototype.transmitGeneralError = function(destination, error) {

    /* Transmit an exception to a destination.
    		
    		    This method is probably not ever useful. It is used to signal a
    		    general fault on the remote connection. Since even the most insecure
    		    public server will want to ignore such Exception, due to the high
    		    potential for abuse, this would probably be used on a client where
    		    the server is fully trusted.
     */
    var outStream;
    outStream = destination.getOutputBuffer();
    outStream.write(headers.HEADER_GENERAL_ERROR);
    error.serializeConstructor(this, outStream);
    return outStream.commit();
  };

  Connection.prototype.handleIncomingMessageError = function(destination, messageID, error) {

    /* Handler for an Exception raised on an incoming Eval/Resolve.
    		
    		    Handler for the situation when an incoming message (an eval or
    		    resolve) has triggered an error, such that the error in question
    		    should be sent as an error reply as a response to the message.
     */
    if (!(error(isinstance(TransverseException)))) {
      return this.bus.handleLocalException(destination, error);
    } else {
      return this.transmitMessageError(destination, messageID, error);
    }
  };

  return Connection;

})();


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


/* @declare bus_single
   *
   * @require bus_base
 */
var SingleBus,
  __hasProp = {}.hasOwnProperty,
  __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };

SingleBus = (function(_super) {
  __extends(SingleBus, _super);

  function SingleBus() {
    return SingleBus.__super__.constructor.apply(this, arguments);
  }


  /* A SingleBus is a Bus with one Transport only.
  	
  	    This class is designed for application that do not need the complexity
  	    of the full routing capabilities of Ripley. To this end, this class only
  	    uses a single transport, to a remote BusMaster and offerer of all the
  	    Services to be used by this bus.
  	
  	    This Bus does not support a local BusMaster.
   */

  SingleBus.prototype.bootstrapOnTransport = function(transport) {

    /* Attaches the Bus to its Transport and makes the sole Connection.
    		
    		    This is the only way to get a Connection for a SingleBus. It is
    		    responsible for bootstrapping the Route, Connection and
    		    MasterService over the BootstrapTransport. It then sets the
    		    supplied transport as the Bus's only Transport, sets the master
    		    and returns the Connection for Services to be discovered on.
     */
    var connection, masterService, remoteBusID, _ref;
    _ref = this.getBootstrapConnection(transport), connection = _ref[0], masterService = _ref[1], remoteBusID = _ref[2];
    this.masterService = masterService;
    this.onlyTransport = transport;
    return connection;
  };

  SingleBus.prototype.resolveTransport = function(busID) {

    /* Tries to resolve the remote busID to this Bus's Transport.
    		
    		    Whereas a FullBus will use this method to map a busID to a Transport
    		    between this bus and the one referenced by the busID, for a
    		    SingleBus, this method only equates to checking that the remote
    		    BusID matches that on the remote end of its sole Transport.
     */
    var otherID;
    otherID = this.onlyTransport.remoteBusID;
    if (busID !== otherID) {
      throw new KeyError("Remote bus was not the right bus. Saw " + busID, "it should be " + otherID);
    }
    return this.onlyTransport;
  };

  return SingleBus;

})(Bus);
