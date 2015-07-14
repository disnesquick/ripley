# System imports
import io

# Local imports
from .serialize import *
from .route     import *

# Exports
__all__ = ["FilterElement", "FilteredResponseRoute"]


class FilterElement(BlackBox):
	""" This is the base class for all filter interfaces.
	
	    Filters are objects which are referenced by the FILTER message type to
	    insert them in the (de)serialization chain between the transport and
	    the argument marshalling code.
	"""

class FilteredResponseRoute(Route):
	def __init__(self, parentRoute, localElement, remoteReference):
		self.parentRoute = parentRoute
		self.lastRoute = parentRoute.lastRoute
		self.localElement = localElement
		self.remoteReference = remoteReference
	
	def getOutputBuffer(self):
		""" Called to get a writeable buffer-filter kludge.
		
		    The writeable buffer represents a filtering of data through to an
		    actual Route-derived buffer. When committed, the local filter
		    element will be applied and the output message will be tagged with
		    the remote element Reference.
		"""
		return Filtered(self)
	
	def applyFilter(self, inStream):
		outStream = self.parentRoute.getOutputBuffer()
		self.localElement.transcode(inStream, outStream)
		return outStream


class FilteredBuffer(io.BytesIO):
	def __init__(self, filteredResponseRoute):
		super().__init__()
		self.route = filteredResponseRoute
		Reference.serialize(self.route.remoteReference, self)
	
	def commit(self):
		self.seek(0)
		return self.route.applyFilter(self).commit()
	
	
	def commitSync(self):
		self.seek(0)
		return self.route.applyFilter(self).commitSync()
