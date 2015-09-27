from ripley.service import *
from ripley.serialize import *


__all__ = [
	"TransportServer",
	"ProspectiveRoute",
	"OpenTransport",
	"OpenRoute",
	"ServiceOffering",
	"BusMaster",
	"BusClientService",
	"BusMasterService"]


class TransportServer(PassByReference):
	pass


class ProspectiveRoute(PassByReference):
	pass


class OpenTransport(PassByReference):
	@staticmethod
	def getProxyClass():
		return OpenTransportProxy


class OpenRoute(PassByReference):
	@staticmethod
	def getProxyClass():
		return OpenRouteProxy


class ServiceOffering(PassByReference):
	@staticmethod
	def getProxyClass():
		return ServiceOfferingProxy


class BusMaster(PassByReference):
	@staticmethod
	def getProxyClass():
		return BusMasterProxy


@implements(OpenTransport)
class OpenTransportProxy(ObjectProxy):
	class accept(MethodNotificationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			cxn.serializeObject(args[0], outStream)
			TransverseID.serialize(args[1], outStream)
	
	accept = accept(b"OpenTransport::accept")
	
	class connect(MethodNotificationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			URI.serialize(args[0], outStream)
			TransverseID.serialize(args[1], outStream)
	
	connect = connect(b"OpenTransport::connect")
	


@implements(OpenRoute)
class OpenRouteProxy(ObjectProxy):
	class supplyEndpointBus(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			BusID.serialize(args[0], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = RouteToken.deserialize(inStream)
			return ret0
	
	supplyEndpointBus = supplyEndpointBus(b"OpenRoute::supplyEndpointBus")
	
	class completeRoute(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			RouteToken.serialize(args[0], outStream)
			ConnectionID.serialize(args[1], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			return 
	
	completeRoute = completeRoute(b"OpenRoute::completeRoute")
	
	class getConnectionID(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = ConnectionID.deserialize(inStream)
			return ret0
	
	getConnectionID = getConnectionID(b"OpenRoute::getConnectionID")
	


@implements(ServiceOffering)
class ServiceOfferingProxy(ObjectProxy):
	class request(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = cxn.deserializeObject(inStream, OpenRoute)
			return ret0
	
	request = request(b"ServiceOffering::request")
	


@implements(BusMaster)
class BusMasterProxy(ObjectProxy):
	class getNeonateID(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = ConnectionID.deserialize(inStream)
			return ret0
	
	getNeonateID = getNeonateID(b"BusMaster::getNeonateID")
	
	class offer(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			cxn.serializeObject(args[0], outStream)
			TransverseID.serialize(args[1], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			return 
	
	offer = offer(b"BusMaster::offer")
	
	class discover(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			TransverseID.serialize(args[0], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			ret0 = cxn.deserializeObject(inStream, ProspectiveRoute)
			return ret0
	
	discover = discover(b"BusMaster::discover")
	
	class connect(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			cxn.serializeObject(args[0], outStream)
			cxn.serializeObject(args[1], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			return 
	
	connect = connect(b"BusMaster::connect")
	
	class requestConnection(MethodNotificationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			cxn.serializeObject(args[0], outStream)
			BusID.serialize(args[1], outStream)
	
	requestConnection = requestConnection(b"BusMaster::requestConnection")
	
	class registerServer(MethodEvaluationProxy):
		@staticmethod
		def serializeArguments(cxn, inst, args, outStream):
			Reference.serialize(inst.reference, outStream)
			cxn.serializeObject(args[0], outStream)
			URI.serialize(args[1], outStream)
		@staticmethod
		def deserializeReturn(cxn, inStream):
			return 
	
	registerServer = registerServer(b"BusMaster::registerServer")
	


class getBusMasterProxy(EvaluationProxy):
	@staticmethod
	def serializeArguments(cxn, args, outStream):
		pass
	@staticmethod
	def deserializeReturn(cxn, inStream):
		ret0 = cxn.deserializeObject(inStream, BusMaster)
		return ret0


class OpenTransportExposed(ExposedObject):
	class accept(ExposedCall):
		transverseID = b"OpenTransport::accept"
		def __call__(self, cxn, inStream):
			__self__ = cxn.deserializeObject(inStream, OpenTransport)
			arg0 = cxn.deserializeObject(inStream, TransportServer)
			arg1 = TransverseID.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	class connect(ExposedCall):
		transverseID = b"OpenTransport::connect"
		def __call__(self, cxn, inStream):
			__self__ = cxn.deserializeObject(inStream, OpenTransport)
			arg0 = URI.deserialize(inStream)
			arg1 = TransverseID.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	exposedMethods = {
		"accept" : accept,
		"connect" : connect
	}


class OpenRouteExposed(ExposedObject):
	class supplyEndpointBus(ExposedCall):
		transverseID = b"OpenRoute::supplyEndpointBus"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, OpenRoute)
			arg0 = BusID.deserialize(inStream)
			ret0 = self.call(__self__, arg0)
			RouteToken.serialize(ret0, outStream)
	
	class completeRoute(ExposedCall):
		transverseID = b"OpenRoute::completeRoute"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, OpenRoute)
			arg0 = RouteToken.deserialize(inStream)
			arg1 = ConnectionID.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	class getConnectionID(ExposedCall):
		transverseID = b"OpenRoute::getConnectionID"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, OpenRoute)
			ret0 = self.call(__self__)
			ConnectionID.serialize(ret0, outStream)
	
	exposedMethods = {
		"supplyEndpointBus" : supplyEndpointBus,
		"completeRoute" : completeRoute,
		"getConnectionID" : getConnectionID
	}


class ServiceOfferingExposed(ExposedObject):
	class request(ExposedCall):
		transverseID = b"ServiceOffering::request"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, ServiceOffering)
			ret0 = self.call(__self__)
			cxn.serializeObject(ret0, outStream)
	
	exposedMethods = {
		"request" : request
	}


class BusMasterExposed(ExposedObject):
	class getNeonateID(ExposedCall):
		transverseID = b"BusMaster::getNeonateID"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			ret0 = self.call(__self__)
			ConnectionID.serialize(ret0, outStream)
	
	class offer(ExposedCall):
		transverseID = b"BusMaster::offer"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			arg0 = cxn.deserializeObject(inStream, ServiceOffering)
			arg1 = TransverseID.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	class discover(ExposedCall):
		transverseID = b"BusMaster::discover"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			arg0 = TransverseID.deserialize(inStream)
			ret0 = self.call(__self__, arg0)
			cxn.serializeObject(ret0, outStream)
	
	class connect(ExposedCall):
		transverseID = b"BusMaster::connect"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			arg0 = cxn.deserializeObject(inStream, OpenRoute)
			arg1 = cxn.deserializeObject(inStream, ProspectiveRoute)
			self.call(__self__, arg0, arg1)
	
	class requestConnection(ExposedCall):
		transverseID = b"BusMaster::requestConnection"
		def __call__(self, cxn, inStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			arg0 = cxn.deserializeObject(inStream, OpenTransport)
			arg1 = BusID.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	class registerServer(ExposedCall):
		transverseID = b"BusMaster::registerServer"
		def __call__(self, cxn, inStream, outStream):
			__self__ = cxn.deserializeObject(inStream, BusMaster)
			arg0 = cxn.deserializeObject(inStream, TransportServer)
			arg1 = URI.deserialize(inStream)
			self.call(__self__, arg0, arg1)
	
	exposedMethods = {
		"getNeonateID" : getNeonateID,
		"offer" : offer,
		"discover" : discover,
		"connect" : connect,
		"requestConnection" : requestConnection,
		"registerServer" : registerServer
	}


class getBusMasterExposed(ExposedCall):
	transverseID = b"::getBusMaster"
	def __call__(self, cxn, inStream, outStream):
		arg0 = GetMyConnection.deserialize(cxn, inStream)
		ret0 = self.call(arg0)
		cxn.serializeObject(ret0, outStream)


class BusClientService(Service):
	transverseID = b"@a1a86905"
	@classmethod
	def getExposed(cls):
		return {
			"OpenTransport" : OpenTransportExposed,
			"OpenRoute" : OpenRouteExposed,
			"ServiceOffering" : ServiceOfferingExposed
		}


class BusMasterService(Service):
	transverseID = b"@3225e3be"
	getBusMaster = getBusMasterProxy(b"::getBusMaster")
	@classmethod
	def getExposed(cls):
		return {
			"BusMaster" : BusMasterExposed,
			"getBusMaster" : getBusMasterExposed
		}


