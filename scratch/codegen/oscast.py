class ASTNode(object):
	def __init__(self, *subNodes, coord=None):
		self.subNodes = subNodes
		self.coord = coord
	def __repr__(self):
		return "%s<%s>"%(type(self).__name__, ",".join([repr(i) for i in self.subNodes]))


class OSCAddress(ASTNode):
	pass


class BasicType(ASTNode):
	def __init__(self, typeDef, coord = None):
		self.typeDef = typeDef
		self.coord = coord
		self.subNodes = typeDef,

	def translateToC(self):
		if self.typeDef in ["bool", "double","float","char"]:
			return self.typeDef
		elif self.typeDef == "int":
			return "int32_t"
		elif self.typeDef == "long":
			return "int64_t"
		elif self.typeDef == "blob":
			return "uint8_t[]"
		elif self.typeDef == "timetag":
			return "uint32_t[]"
		elif self.typeDef == "string":
			return "char[]"

	def assignVarName(self, varName):
		self.varName = varName

	def getCDeclaration(self):
		if self.typeDef in ["bool", "double","float", "char"]:
			return "\t%s %s;\n"%(self.typeDef, self.varName)
		elif self.typeDef == "int":
			return "\tint32_t %s;\n"%self.varName
		elif self.typeDef == "timetag":
			return "\tuint32_t %s[2];\n"%self.varName
		elif self.typeDef == "long":
			return "\tint64_t %s;\n"%self.varName
		elif self.typeDef == "blob":
			return "\tuint8_t %s[OSC_MAX_BLOB_SIZE];\nint %s_length;\n"%(self.varName, self.varName)
		elif self.typeDef == "string":
			return "\tchar %s[OSC_MAX_STRING_SIZE];\n"%self.varName

	def readCCode(self):
		if self.typeDef == "bool":
			fname = "OSCReadBool"
		elif self.typeDef == "int":
			fname = "OSCReadInt"
		elif self.typeDef == "char":
			fname = "OSCReadChar"
		elif self.typeDef == "long":
			fname = "OSCReadLong"
		elif self.typeDef == "float":
			fname = "OSCReadFloat"
		elif self.typeDef == "double":
			fname = "OSCReadDouble"
		elif self.typeDef == "blob":
			return "OSCReadBlob(stream, %s);\n"%self.varName
		elif self.typeDef == "string":
			return "OSCReadString(stream, %s);\n"%self.varName
		elif self.typeDef == "timetag":
			return "OSCReadTimeTag(stream, %s);\n"%self.varName
		else:
			raise(Exception("%s unsupported type"%self.typeDef))
		
		return "%s = %s(stream);\n" % (self.varName, fname)

	def getOSCTag(self):
		if self.typeDef == "bool":
			return "T"
		if self.typeDef == "char":
			return "c"
		elif self.typeDef == "int":
			return "i"
		elif self.typeDef == "long":
			return "h"
		elif self.typeDef == "float":
			return "f"
		elif self.typeDef == "double":
			return "d"
		elif self.typeDef == "string":
			return "s"
		elif self.typeDef == "blob":
			return "b"
		elif self.typeDef == "timetag":
			return "t"
		else:
			raise(Exception("%s unsupported type"%self.typeDef))


class OSCDefinition(ASTNode):
	addrNumber = 0
	def __init__(self, address, cfunc, typeDef, coord = None):
		self.addrNumber = type(self).addrNumber
		type(self).addrNumber += 1
		self.address = address
		self.cfunc = cfunc
		self.typeDef = typeDef
		self.coord = coord
		self.subNodes = (address,cfunc,typeDef)
		self.varNames = False
	
	def getFuncProto(self):
		build = [td.translateToC() for td in self.typeDef]
		if build > []:
			return "extern int %s(OSCStream,%s);\n" % (self.cfunc, ",".join(build))
		else:
			return "extern int %s(OSCStream);\n" % self.cfunc

	def getTagString(self):
		return "".join([","]+[td.getOSCTag() for td in self.typeDef])
			

	def getTmpVarDefs(self):
		return [td.getCDeclaration() for td in self.typeDef]


	def assignVarNames(self):
		idx = 0
		for i in self.typeDef:
			i.assignVarName("tmpVar_%d"%idx)
			idx += 1
		self.varNames = True
	
	def getHookCall(self):
		if self.typeDef > []:
			return "\treturn %s(stream,%s);\n"%(self.cfunc, ",".join([td.varName for td in self.typeDef]))
		else:
			return "\treturn %s(stream);\n"%(self.cfunc)

	def getFillTmpVars(self):
		return ["\t"+td.readCCode() for td in self.typeDef]

	def outputFuncCallHook(self):
		if not self.varNames:
			self.assignVarNames()
		build = []
		build.append(self.getFuncProto())
		build.append("char addressString_%d[]=\"%s\";\n"%(self.addrNumber,"/"+"/".join(self.address.subNodes[0])))
		build.append("int hook_%d(OSCStream stream) {\n"%self.addrNumber)
		build = build + self.getTmpVarDefs()
		build.append("\tstream->address = addressString_%d;\n"%self.addrNumber)
		build.append("\tif (OSCStreamEntry(\"%s\", stream, NULL))\n"%(self.getTagString()))
		build.append("\t\treturn OSC_ERROR_TAG_MISMATCH;\n")
		build = build + self.getFillTmpVars()
		
		build.append(self.getHookCall())
		build.append("}\n")
		return "".join(build)


class AddressNode:
	badList=" #*,/?[]{}"
	@staticmethod
	def stringCheck(string):
		for i in AddressNode.badList:
			if i in string:
				return True
		return False


	def __init__(self):
		self.children = []
		self.leaf = None
		self.subs = []
	def indentedPrint(self, indent = 0):
		for string,node in self.children:
			print("%s%s"%(indent*"\t",string))
			node.indentedPrint(indent+1)


class AddressTree(AddressNode):
	def addDefinition(self, definition):
		matchList = definition.address.subNodes[0]
		value = definition
		curNode = self
		for curString in matchList:
			foundNode = None
			for string, node in curNode.children:
				if curString == string:
					foundNode = node
					break
			if foundNode == None:
				if self.stringCheck(curString):
					raise(Exception("Bad character in %s"%curString))
				foundNode = AddressNode()
				curNode.children.append((curString, foundNode))
			curNode = foundNode
		if curNode.leaf:
			raise(Exception)
		curNode.leaf = value
	
	def buildOutputCode(self):
		curStack = []
		build = []
		count = 1
		curStack.append((self,0))
		
		preBuild = []
		while curStack > []:
			cur,thisVal = curStack.pop()
			if thisVal > 0:
				name = "treeCall_%d"%thisVal
				preBuild.append("int %s(OSCStream stream, char*);\n"%name)
			else:
				name = "treeCallRoot"
			build.append("int %s(OSCStream stream, char* curString) {\n"%name)
			build.append("\tint ret = 0;\n")
			if len(cur.children) > 0:
				build.append("\tchar* nextString;\n")
			for unitName, child in cur.children:
				childVal = count
				count += 1
				curStack.append((child, childVal))
				build.append("\tif ((nextString = OSCMatchAddressUnit(curString, \"%s\")) != NULL)\n"%unitName)
				build.append("\t\tret += treeCall_%d(stream, nextString);\n"%childVal)
			if cur.leaf:
				build.append("\tif (*curString == '\\0') {\n")
				build.append("\t\tstream->seek(stream->savePos);\n")
				build.append("\t\tstream->count++;\n")
				build.append("\t\tret += hook_%s(stream);\n"%cur.leaf.addrNumber)
				build.append("\t}\n")
			build.append("\treturn ret;\n}\n\n")
		return "".join(preBuild+["\n"]+build)
		
