#!/usr/bin/python

# System imports
import argparse

# Local imports
from parser import RipleyParser
from process import *
from cpp import *

parser = argparse.ArgumentParser(description="Generate code from an IDL file")
parser.add_argument(dest="inFile", metavar='INFILE', type=str,
                    help="input definition file")
parser.add_argument(dest="outFile",metavar='OUTFILE', type=str,
                    help="output code file")

args = parser.parse_args()

parser = RipleyParser()

inText = open(args.inFile,"r").read()
inStructure = parser.parse(inText)
baseTypeMap = buildBaseMap()
processed = Processed(inStructure, baseTypeMap, AbstractCompiler,
                      ObjectCompiler, ExceptionCompiler)
oHandle = open(args.outFile, "w")

buildOutput(processed, oHandle)

oHandle.close()
