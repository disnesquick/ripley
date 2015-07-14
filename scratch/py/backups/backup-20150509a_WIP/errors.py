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
	def __constructor__(string:UnicodeString):
		pass


@implements(SerializedErrorInterface)
class SerializedError(TransverseException):
	def __init__(self, thing):
		self.string = repr(thing)

	def remoteClone(self):
		return SerializedErrorInterface.newRemote(self.string)




errorList = [
	(UnknownErrorInterface, UnknownError),
	(SerializedErrorInterface, SerializedError)
]
