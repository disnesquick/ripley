import asyncio
import io

class TransportClosed(Exception):
	""" This exception is raised on the router poling coroutine when the transport is closed
	    by either end, to cause an exit from the loop.
	"""


class Transport:
	def startWrite(self):
		return io.BytesIO()

	@asyncio.coroutine
	def commitWrite(self, message):
		yield from self.send(message.getvalue())
