import argparse
from oscparser import OSCParser
from oscast import AddressTree

parser = argparse.ArgumentParser(description="raster-slice an SVG from Slic3r into a set of images")
parser.add_argument(dest="inFile", metavar='INFILE', type=str,  help="input definition file")
parser.add_argument(dest="outFile",metavar='OUTFILE', type=str,  help="output C file")
	
args = parser.parse_args()

parser = OSCParser()
inText = open(args.inFile,"r").read()
inStructure = parser.parse(inText)


outHandle = open(args.outFile,"w")
outHandle.write("#include <stdlib.h>\n")
outHandle.write("#include <libosc.h>\n")
outTree = AddressTree()
seenCFuncs = set()
for td in inStructure:
	outTree.addDefinition(td)
	outHandle.write(td.outputFuncCallHook())
outTree.indentedPrint()
outHandle.write(outTree.buildOutputCode())
outHandle.close()
