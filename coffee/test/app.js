(function() {
  var app, exampleSocket, gateway, gogo, proxy, socket, testImplementation, testIsh, transcoder;

  app = angular.module('myapp', []);

  testIsh = new ShareableObjectInterface("Test", null, {
    constructor: new CallInterface([], Int32),
    echo: new CallInterface([UnicodeString], UnicodeString)
  });

  testImplementation = (function() {
    testImplementation.prototype.__implementation_of__ = testIsh;

    function testImplementation(a) {
      this.a = a;
    }

    testImplementation.prototype.echo = function(msg) {
      throw new UnknownMessageIDError("FUCK");
      this.a += 1;
      return "" + msg + ":" + this.a;
    };

    return testImplementation;

  })();

  proxy = testIsh.getProxyClass();

  gogo = function() {
    var a;
    a = gateway.runCall(testIsh.requestNew(1));
    console.log(a);
    return a.then(function(z) {
      var y;
      console.log("result");
      console.log(z);
      y = z.echo("hello");
      console.log(y);
      return y;
    }).then(function(y) {
      return console.log(y);
    });
  };

  transcoder = new StaticTranscoder;

  socket = new WebSocket("ws://localhost:8765");

  exampleSocket = new WebsocketTransport(socket);

  gateway = new TransportGateway(transcoder, exampleSocket, true);

  gateway.exposeObjectImplementation(testImplementation);

  app.controller("TodoCtrl", function($scope) {
    return $scope.$watch('one * two', function(value) {
      return $scope.total = JSON.stringify(Promise) + value;
    });
  });

}).call(this);
