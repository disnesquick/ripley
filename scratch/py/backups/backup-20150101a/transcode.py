from serialize import *
import io
class LineTranscoder:
	def encode(self, obj):
		raise(Exception("%s did not define the 'encode' method"%type(self)))
	
	def decode(self, msg):
		raise(Exception("%s did not define the 'decode' method"%type(self)))


class StaticTranscoder(LineTranscoder):
	def encode(self, obj, outStream):
		if not isinstance(obj, EncodingTypeBinding):
			raise(TypeError("Expected EncodingTypeBinding not a %s"%(type(obj))))
		for obj, typ in obj.getZipped():
			typ.encodeStatic(obj, outStream)

	def decode(self, obj):
		ret = []
		source = obj.data
		for typ in obj.typeTuple:
			ret.append(typ.decodeStatic(source))
		return ret 

	def decodeSingle(self, typ, source):
		return typ.decodeStatic(source)

	def encodeSingle(self, typ, obj, outStream):
		typ.encodeStatic(obj, outStream)
