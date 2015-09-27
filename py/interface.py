from unstuck import *

class ExposedCall:
	def __init__(self, func):
		self.call = func
	
	def __call__(self, *args, **kwargs):
		raise(NotImplementedError)


class ExposedObject:
	exposedMethods = {}
	def __call__(self, *args, **kwargs):
		raise(NotImplementedError)


class BoundMethod:
	def __init__(self, instance, proxy):
		self.instance = instance
		self.proxy = proxy
	
	def __call__(self, *args):
		return await(self.proxy.handleCall(self.instance, args))
	
	def async(self, *args):
		return async(self.proxy.handleCall(self.instance, args))
	
	def coro(self, *args):
		return self.proxy.handleCall(self.instance, args)


class BoundCall:
	def __init__(self, route, proxy):
		self.route = route
		self.proxy = proxy
	
	def __call__(self, *args):
		return await(self.proxy.handleCall(self.route, args))
	
	def async(self, *args):
		return async(self.proxy.handleCall(self.route, args))
	
	def coro(self, *args):
		return self.proxy.handleCall(self.route, args)


class MethodProxy:
	def __init__(self, transverseID):
		self.transverseID = transverseID
	
	def __get__(self, instance, owner):
		return BoundMethod(instance, self)


class CallProxy:
	def __init__(self, transverseID):
		self.transverseID = transverseID
	
	def __get__(self, instance, owner):
		return BoundCall(instance.destination, self)


class NotificationProxy(CallProxy):
	@asynchronous
	def handleCall(self, route, args):
		connection = route.connection
		objectID = yield from connection.transceiveResolve(
		                                      route, self.transverseID)
		outStream = connection.transmitNotify(route, objectID)
		self.serializeArguments(connection, args, outStream)
		outStream.commit()


class MethodNotificationProxy(MethodProxy):
	@asynchronous
	def handleCall(self, instance, args):
		route = instance.destination
		connection = route.connection
		objectID = yield from connection.transceiveResolve(
		                                      route, self.transverseID)
		outStream = connection.transmitNotify(route, objectID)
		self.serializeArguments(connection, instance, args, outStream)
		outStream.commit()


class EvaluationProxy(CallProxy):
	@asynchronous
	def handleCall(self, route, args):
		connection = route.connection
		
		# Resolve the TransverseID to a CallID
		objectID = yield from connection.transceiveResolve(
		                                      route, self.transverseID)
		
		# Transmit the remote call
		outStream, responseFuture = connection.transceiveEval(route, objectID)
		self.serializeArguments(connection, args, outStream)
		outStream.commit()
		
		# Wait for the reply and deserialize the return or throw an exception
		# if this failed.
		inStream = yield from responseFuture
		return self.deserializeReturn(connection, inStream)


class MethodEvaluationProxy(MethodProxy):
	@asynchronous
	def handleCall(self, instance, args):
		""" Sends the argument-bound call to a specific gateway for execution
		    on the remote end.
		"""
		route = instance.destination
		connection = route.connection
		
		# Resolve the TransverseID to a CallID
		objectID = yield from connection.transceiveResolve(
		                                      route, self.transverseID)
		
		# Transmit the remote call
		outStream, responseFuture = connection.transceiveEval(route, objectID)
		self.serializeArguments(connection, instance, args, outStream)
		outStream.commit()
		
		# Wait for the reply and deserialize the return or throw an exception
		# if this failed.
		inStream = yield from responseFuture
		return self.deserializeReturn(connection, inStream)
