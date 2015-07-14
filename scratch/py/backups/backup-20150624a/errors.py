# Local imports
from .serialize import *
from .share     import *
from .service   import Service

class TransverseException(Exception):
	""" An Exception that can be marshalled as a response to a remote call.
	
	    Base class for exceptions that should be sent for handling on the other
	    side of the route rather than being handled on the side that raised
	    them. When an ExposedCallable completes by raising a
	    TransverseException, then this will be marshalled and sent as the
	    message response.
	"""
	def remoteClone(self):
		""" Produce a clone of the Exception on the remtoe end of the Route.
		
		    remoteClone is a general interface which allows local objects to be
		    re-created on the remote side. It takes no parameters and returns
		    a RemoteEval object from the `share' module which can then be
		    applied to a Route.
		"""
		cls = type(self)
		args = self.remoteCloneArgs()
		return RemoteEval(cls.teIFace, args, {})
	
	def serializeConstructor(self, connection, outStream):
		iface = type(self).teIFace
		TransverseID.serialize(iface.transverseID, outStream)
		args = self.remoteCloneArgs()
		iface.serializeArguments(connection, args, outStream)
	
	def remoteCloneArgs(self):
		""" Get the arguments for remoteClone.
		
		    TransverseExceptions use the teImplements rather than `implements'.
		    This sets the Interface to remote clone on the remote side of
		    the Route. The other part of the remote clone needed is the set
		    of arguments for the Interface constructor. This private function
		    is used to provide them. Default is no arguments.
		"""
		return ()


def teImplements(iface):
	""" Use for TransverseExceptions in place of `implements'
	
	    This wrapper functions in the same way as the basic `implements' with
	    the additional behaviour of setting the cls.teIFace property to the
	    constructor call interface so that the Exception can be remote cloned.
	    All TransverseExceptions must be remote cloneable.
	"""
	def inner(cls):
		cls.teIFace = iface.getCallInterface()
		return implements(iface)(cls)
	return inner


class TransverseExceptionInterface(TransverseObjectInterface):
	""" Base interface for exception interfaces.
	
	    All defined exception interfaces should inherit from this (blank)
	    template.
	"""


class UnknownErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownError
	"""
	def __constructor__():
		pass


@teImplements(UnknownErrorInterface)
class UnknownError(TransverseException):
	""" A fall-back error to raise when something has gone wrong but the local side doesn't
	    want the remote side to know what happened. Used for application which don't want to
	    leak information to potential attackers.
	"""


class ErrorUnsupportedInterface(TransverseExceptionInterface):
	""" Interface for ErrorUnsupported
	"""
	def __constructor__(errorID: TransverseID):
		pass


@teImplements(ErrorUnsupportedInterface)
class ErrorUnsupported(TransverseException):
	def __init__(self, errorID):
		self.errorID = errorID
	
	def remoteCloneArgs(self):
		return self.errorID,


class SerializedErrorInterface(TransverseExceptionInterface):
	""" Interface for SerializedError.
	"""
	def __constructor__(string:UnicodeString):
		pass


@teImplements(SerializedErrorInterface)
class SerializedError(TransverseException):
	""" An error useful for debugging. Converts the object in question (intended to be a language
	    exception) into a string and sends it down the wire.
	"""
	def __init__(self, thing):
		self.string = repr(thing)
	
	def remoteCloneArgs(self):
		return self.string,


class UnknownMessageIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownMessageIDError.
	"""
	def __constructor__(messageID:MessageID):
		pass


@teImplements(UnknownMessageIDErrorInterface)
class UnknownMessageIDError(TransverseException):
	""" This error is raised when an incoming reply or error, supposedly associated with an
	    outgoing message, does not match any outgoing message, waiting to be serviced, on the
	    local end of the route.
	"""
	def __init__(self, messageID):
		self.messageID = messageID
	
	def remoteCloneArgs(self):
		return self.messageID,


class UnknownTransverseIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownTransverseIDError.
	"""
	def __constructor__(tranverseID:TransverseID):
		pass


@teImplements(UnknownTransverseIDErrorInterface)
class UnknownTransverseIDError(TransverseException):
	""" This error is raised when an incoming tranverse resolution request, or an immediate
	    transverse reference within another message, requests a transverse ID that is not
	    exposed on the local side.
	"""
	def __init__(self, transverseID):
		self.transverseID = transverseID
	
	def remoteCloneArgs(self):
		return self.transverseID,


class UnknownObjectIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownObjectIDError.
	"""
	def __constructor__(objectID:SerialID):
		pass


@teImplements(UnknownObjectIDErrorInterface)
class UnknownObjectIDError(TransverseException):
	""" This error is raised when an incoming message includes a reference where the reference
	    is local but the reference number does not match a local object that has been shared
	    across the router.
	"""
	def __init__(self, objectID):
		self.objectID = objectID
	
	def remoteCloneArgs(self):
		return self.objectID,


class BasicErrorService(Service):
	ErrorUnsupported = ErrorUnsupportedInterface
	UnknownError = UnknownErrorInterface
	SerializedError = SerializedErrorInterface
	UnknownMessageIDError = UnknownMessageIDErrorInterface
	UnknownTransverseIDError = UnknownTransverseIDErrorInterface
	UnknownObjectIDError = UnknownObjectIDErrorInterface

basicErrorService = BasicErrorService.implementation(
	ErrorUnsupported = ErrorUnsupported,
	UnknownError = UnknownError,
	SerializedError = SerializedError,
	UnknownMessageIDError = UnknownMessageIDError,
	UnknownTransverseIDError = UnknownTransverseIDError,
	UnknownObjectIDError = UnknownObjectIDError
)

