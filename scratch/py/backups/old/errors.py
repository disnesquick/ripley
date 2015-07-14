from serialize import *
from shared import *

class TransverseException(Exception):
	""" Base class for exceptions that should be sent for handling on the other side of the
	    route rather than being handled on the side that raised them.
	"""
	def remoteClone(self):
		""" remoteClone is a general interface which allows local objects to be re-created
		    on the remote side. It takes no parameters and should return a RemoteCall object from
		    the shared module which can then be sent to a server.
		"""
		raise(Exception("Transverse exception must implement remoteClone"))


class TransverseExceptionInterface(TransverseObjectInterface):
	""" Base interface for exception interfaces. All defined exception interfaces should
	    inherit from this (blank) template.
	"""


class UnknownErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownError
	"""
	def __constructor__():
		pass


@implements(UnknownErrorInterface)
class UnknownError(TransverseException):
	""" A fall-back error to raise when something has gone wrong but the local side doesn't
	    want the remote side to know what happened. Used for application which don't want to
	    leak information to potential attackers.
	"""
	def remoteClone(self):
		return UnknownErrorInterface.newRemote()


class SerializedErrorInterface(TransverseExceptionInterface):
	""" Interface for SerializedError.
	"""
	def __constructor__(string:UnicodeString):
		pass


@implements(SerializedErrorInterface)
class SerializedError(TransverseException):
	""" An error useful for debugging. Converts the object in question (intended to be a language
	    exception) into a string and sends it down the wire.
	"""
	def __init__(self, thing):
		self.string = repr(thing)

	def remoteClone(self):
		return SerializedErrorInterface.newRemote(self.string)


class UnknownMessageIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownMessageIDError.
	"""
	def __constructor__(messageID:MessageID):
		pass


@implements(UnknownMessageIDErrorInterface)
class UnknownMessageIDError(TransverseException):
	""" This error is raised when an incoming reply or error, supposedly associated with an
	    outgoing message, does not match any outgoing message, waiting to be serviced, on the
	    local end of the route.
	"""
	def __init__(self, messageID):
		self.messageID = messageID

	def remoteClone(self):
		return UnknownMessageIDErrorInterface.newRemote(self.messageID)


class UnknownTransverseIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownTransverseIDError.
	"""
	def __constructor__(tranverseID:TransverseID):
		pass


@implements(UnknownTransverseIDErrorInterface)
class UnknownTransverseIDError(TransverseException):
	""" This error is raised when an incoming tranverse resolution request, or an immediate
	    transverse reference within another message, requests a transverse ID that is not
	    exposed on the local side.
	"""
	def __init__(self, transverseID):
		self.transverseID = transverseID

	def remoteClone(self):
		return UnknownTransverseIDErrorInterface.newRemote(self.transverseID)


class UnknownObjectIDErrorInterface(TransverseExceptionInterface):
	""" Interface for UnknownObjectIDError.
	"""
	def __constructor__(objectID:ObjectID):
		pass


@implements(UnknownObjectIDErrorInterface)
class UnknownObjectIDError(TransverseException):
	""" This error is raised when an incoming message includes a reference where the reference
	    is local but the reference number does not match a local object that has been shared
	    across the router.
	"""
	def __init__(self, objectID):
		self.objectID = objectID

	def remoteClone(self):
		return UnknownObjectIDErrorInterface.newRemote(self.objectID)


errorList = [
	(UnknownErrorInterface, UnknownError),
	(SerializedErrorInterface, SerializedError),
	(UnknownMessageIDErrorInterface, UnknownMessageIDError),
	(UnknownTransverseIDErrorInterface, UnknownTransverseIDError),
	(UnknownObjectIDErrorInterface, UnknownObjectIDError)
]
