from shared import *
from transport import Transport
import headers
import io

class FilterElement(TransverseObjectInterface):
	""" This is the base class for all filter types, filters are objects
	    which are referenced by the FILTER message type to insert them
	    in the decoding chain between the transcoder and the transport.
	"""

class Filter:
	""" This is the class that handles the actual creation of a filter
	    object directly usable by the FILTER message type. It takes two
	    filter elements, one for the decoding of the incoming messages
	    and one for the encoding of outgoing messages.
	"""
	def __init__(self, localElement, remoteElement):
		self.localElement = localElement
		self.remoteElement = remoteElement

class DummyElement:
	@staticmethod
	def transcode(value):
		return value


class FilterTypeBindingKludge(SerializableType):
	""" An object that binds a filter pair (sender and receiver) so that the serial
	    stream can encoded and bound to a filter message type with reception decoder
	    and optionally reply encoder.
	"""
	@staticmethod
	def encodeStatic(value, outStream):
		""" This is actually a cunning way of coding stuff. Sheesh, my comment-mojo
		    is fucked tonight.
		"""
		newContents = value.applyElement.transcode(outStream.getvalue())
		outStream.seek(0,io.SEEK_SET)
		outStream.truncate(0)
		outStream.write(value.header)
		outStream.write(newContents)

class FilterOutputTypeBindingKludge(FilterTypeBindingKludge):
	""" This is a binding kludge that will add a FILTER_OUT tag to the message so that the response will
	    be returned through that temporary pipeline (i.e. it will be encoded with the remote
	    element and marked for decode by the local element.
	"""
	def __init__(self, transportGateway, filter):
		tempHeader = io.BytesIO()
		tempHeader.write(headers.HEADER_FILTER_OUT)
		remoteFilterID = transportGateway.shareObject(filter.remoteElement)
		localFilterID = transportGateway.shareObject(filter.localElement)
		transportGateway.transcoder.encodeSingle(ObjectID, remoteFilterID, tempHeader)
		transportGateway.transcoder.encodeSingle(ObjectID, localFilterID, tempHeader)
		self.header = tempHeader.getvalue()
		self.applyElement = DummyElement

class FilterInputTypeBindingKludge(FilterTypeBindingKludge):
	""" This is a binding kludge that will add a FILTER_IN tag to the message so that the message will
	    be transcoded by the local filter element and marked for decoding at the other end by the
	    remote filter element.
	"""
	def __init__(self, transportGateway, filter):
		tempHeader = io.BytesIO()
		tempHeader.write(headers.HEADER_FILTER_IN)
		remoteFilterID = transportGateway.shareObject(filter.remoteElement)
		transportGateway.transcoder.encodeSingle(ObjectID, remoteFilterID, tempHeader)
		self.header = tempHeader.getvalue()
		self.applyElement = filter.localElement

class FilterOutputTransportKludge:
	""" This is a binding kludge that will handle binding an encoder and a remote decoder to a
	    response transport.
	"""
	def __init__(self, filterElement, filterElementBundle, innerTransport, transportGateway):
		self.inner = innerTransport
		self.filterElement = filterElement

		tempHeader = io.BytesIO()
		remoteFilterID = transportGateway.shareObject(filterElementBundle)
		transportGateway.transcoder.encodeSingle(ObjectID, remoteFilterID, tempHeader)
		self.header = tempHeader.getvalue()

	def beginWrite(self, messageType):
		neonate = io.BytesIO()
		neonate.write(messageType)
		return neonate

	def commitWrite(self, message):
		transcoded = self.filterElement.transcode(message.getvalue())
		innerStream = self.inner.beginWrite(headers.HEADER_FILTER_IN)
		innerStream.write(self.header + transcoder)
		return self.inner.commitWrite(innerStream)
