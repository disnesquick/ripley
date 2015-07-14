class UpDict:
	def __init__(self, parents = []):
		self.parents = parents
		self.ownDict = {}
	def __setitem__(self, key, value):
		self.ownDict[key] = value
	def __getitem__(self, key):
		if key in self.ownDict:
			return self.ownDict[key]
		else:
			for i in self.parents:
				try:
					return i[key]
				except KeyError:
					pass
		raise KeyError(key)
	def __iter__(self):
		for base in self.parents:
			yield from base
		yield from self.ownDict

	def items(self):
		for base in self.parents:
			yield from base.items()
		yield from self.ownDict.items()


