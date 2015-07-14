### @declare transcode
  #
  # @require util
###

class LineTranscoder

class StaticTranscoder extends LineTranscoder
	encode: (bound, outStream) ->
		for k in bound.zipped
			val = k[0]
			typ = k[1]
			typ.encodeStatic(val, outStream)
	
	decode: (bound) ->
		r = []
		source = bound.dataStream
		for typ in bound.typeTuple
			val = typ.decodeStatic(source)
			r.push(val)
		r

	decodeSingle: (typ, source) ->
		typ.decodeStatic(source)

	encodeSingle: (typ, val, outStream) ->
		typ.encodeStatic(val, outStream)
