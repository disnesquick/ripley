app = angular.module 'myapp', []


testIsh = new ShareableObjectInterface "Test", null,
	constructor : new CallInterface [], Int32
	echo : new CallInterface [UnicodeString], UnicodeString

class testImplementation
	__implementation_of__ : testIsh
	constructor: (a) ->
		@a = a
	echo : (msg) ->
		throw new UnknownMessageIDError("FUCK")
		@a += 1
		"#{ msg }:#{ @a }"


proxy = testIsh.getProxyClass()

gogo = () ->
	a = gateway.runCall(testIsh.requestNew(1))
	console.log(a)
	a.then (z) ->
		console.log("result")
		console.log(z)
		y = z.echo("hello")
		console.log(y)
		return y
	.then (y) ->
		console.log(y)

transcoder = new StaticTranscoder
socket =  new WebSocket("ws://localhost:8765")
#socket.onopen = gogo
exampleSocket = new WebsocketTransport socket
gateway = new TransportGateway transcoder, exampleSocket, true
gateway.exposeObjectImplementation(testImplementation)

app.controller "TodoCtrl", ($scope) ->
	$scope.$watch 'one * two', (value) ->
		$scope.total = JSON.stringify(Promise) + value
