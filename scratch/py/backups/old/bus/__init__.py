import io
from connection import Connection
from serialize import *
from unstuck import *

class TransportClosed(Exception):
	pass

class Bus:
	def __init__(self):
		self.services = {}
		self.loop = async(self.activeLoop())

