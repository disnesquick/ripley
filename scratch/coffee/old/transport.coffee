### @declare transport
  #
  # @require util
  # @require error
###

class WebsocketTransport
	constructor : (websocket) ->
		@websocket = websocket
		self  = @
		websocket.onmessage = (message) ->
			self.resolve(message)
		websocket.onerror = (error) ->
			self.exception(error)
		@receiveCallback = @receiveFailure
		@errorCallback = @receiveFailure
	
	setCallbacks : (recvHook, errorHook) ->
		@receiveCallback = recvHook
		@errorCallback = errorHook

	receiveFailure : (message) ->
		alert("could not deliver #{ message }")

	resolve : (message) ->
		reader = new FileReader()
		cb = @receiveCallback
		reader.onload = () ->
			cb(new StringIO(reader.result))
		reader.readAsBinaryString(message.data)

	send : (msg) ->
		@websocket.send(stringToArrayBuffer(msg.value))

	beginWrite : () ->
		new StringIO(null)

	hangUp : () ->
		@websocket.close()
