class Broker:
	__default_parent__ = None
	def __init__(self, parent = None):
		""" parent only applies to transverse dictionary """
		if parent == None:
			parent = type(self).__default_parent__

		self.parent = parent
		self.remoteTransverseMap = {}
		self.exposedTransverseMap = {}
		self.exposedObjects = {}
		if parent is not None:
			self.sharedCount = parent.sharedCount
		else:
			self.sharedCount = -1

	def generateShareID(self):
		""" Generates an object ID in the form of a byte-string. Object IDs consist of the gateway tag plus
		    a unique code for the object itself. This allows objects to be mapped to a particular
		    end-point of the gateway.
		    TODO: when a sufficient buffer length has passed, reset the message ID counter.
		"""
		self.sharedCount += 1
		return SerialID.integersToBytes(self.destID, self.sharedCount)

	def exposeObjectImplementation(self, cls):
		""" Exposes a python object that has been marked as an implementation of an object
		    to the other side(s) of the transport. If the interface is marked as
		    non-constructable, then no constructor method will be made available.
		"""
		iface = cls.__implementation_of__
		# TODO Old code: allows implementation of multiple targets in one TODO
		# TODO iface = cls.__implementation_of__[0]                       TODO
		for name, member in iface.__iface_members__.items():
			uuid = member.__transverse_id__
			if name != "__constructor__":
				self.exposedTransverseMap[uuid] = self.shareObject(ExposedCall(getattr(cls,name), member))

		# If the object has a constructor then expose the object class as
		# its function 
		if "__constructor__" in iface.__iface_members__:
			member = iface.__iface_members__["__constructor__"]
			uuid = member.__transverse_id__
			self.exposedTransverseMap[uuid] = self.shareObject(ExposedCall(cls, member))
 
	def referenceObjectList(self, orderedArgs, sharedIndices):
		""" If there are ShareableObjectInterface derived objects in the list, then these
		    should be translated into their shared IDs instead
		"""
		for idx in sharedIndices:
			orderedArgs[idx] = self.referenceObject(orderedArgs[idx])
		return orderedArgs

	def referenceObject(self, obj):
		""" Marks an object as a shared object and stores it in the shared object
		    list for retrieval through an object reference.
		"""
		if hasattr(obj, "__shared_id__"):
			return obj.__shared_id__
		obj.__shared_id__ = shareID = self.generateShareID()
		self.exposedObjects[shareID] = obj
		return shareID


	def dereferenceObjectList(self, orderedArgs, orderedTypes, sharedIndices):
		""" Go through the arguments that have been returned from the remote end and translate
		    objects that have a ShareableObjectInterface annotation into either proxies (for
		    objects on the remote side of the gateway), or into the exposed objects (for objects
		    that have previously been shared)
		"""
		for idx in sharedIndices:
			orderedArgs[idx] = self.dereferenceObject(orderedArgs[idx], orderedTypes[idx])
		return orderedArgs


	def dereferenceObject(self, arg, typ):
		if arg in self.exposedObjects:
			arg = self.exposedObjects[arg]
			if not typ.implementedBy(arg):
				raise(Exception("%s was not of type %s as specified in the interface"%(arg, typ)))
		else:
			arg = typ.getProxyClass()(self, arg)
		return arg

SharedObjectBroker.__default_parent__ = defaultParent = SharedObjectBroker()

defa
	   UnknownError,
	   SerializedError,
	   UnknownMessageIDError,
	   UnknownTransverseIDError,
	   UnknownObjectIDError,
	   DecodingError,
	   EncodingError,
	   TransmissionError


