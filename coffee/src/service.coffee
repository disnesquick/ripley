pushExposedFromBases = (dict, bases, seen) ->
	for base of bases
		if not base in seen
			seen.push(base)
			pushExposedFromBases(dict, base.parentServices, seen)

defineService = (name, bases, nameSpace) ->
	### Define a new Service interface.
	
	    On definition of a new Service class, the parents are inspected and
	    interfaces exposed by those parent Services are collated into a
	    dictionary. The properties of the class are theninspected and those that
	    are not special properties (i.e. With names surrounded by double
	    underscores '__property__') are added to the dictionary.
	###
	_exposedInterfaces = {}
	
	# Enumerate the interfaces from the parents and bundle them together
	# into this class's exposedInterfaces.
	pushExposedFromBases(_exposedInterfaces, bases, [])
	
	# Enumerate the properties from this class and add them into the
	# the exposedInterfaces dictionary.
	for key,value of nameSpace.items():
		_exposedInterfaces[key] = value
	
	class neonate
		@serviceName = "SERVICE::" + name
		@exposedInterfaces = _exposedInterfaces
		@parentServices = bases
	
	for key,value of _exposedInterfaces
		neonate::[key] = _callableStub(value)
	
	neonate


_callableStub = (value) ->
	iface = value.getCallInterface()
	call = value.getBoundCallableClass()
	call(iface)
