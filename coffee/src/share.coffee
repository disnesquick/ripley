class BoundCallable:
	def __init__(self, route, iface):
		self.route = route
		self.iface = iface
	
	def __call__(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return await(remoteCall.callOn(self.route))
	
	def async(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return async(remoteCall.callOn(self.route))
	
	def coro(self, *args, **kwargs):
		remoteCall = self.getCall(args, kwargs)
		return remoteCall.callOn(self.route)


boundEvaluation = (iface) ->
	(args...) ->
		RemoteEval(iface, args).callOn(@destination)

boundMethodEvaluation = (iface) ->
	(args...) ->
		args.unshift(this)
		RemoteEval(iface, args).callOn(@destination)


boundEvaluation = (route, iface)
	(args...) ->
		RemoteEval(iface, args).callOn(route)
