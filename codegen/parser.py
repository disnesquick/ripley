""" Module:  parser.py
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file defines a parser for the Ripley code generator, using the ply
    library.
"""

# External imports
from ply import yacc

# Local imports
from lexer import RipleyLexer
from ast import *

# Exports
__all__ = ["RipleyParser"]


class Coord(object):
	""" Coordinates of a syntactic element.
	
	    Consists of:
	        - File name
	        - Line number
	        - (optional) column number, for the Lexer
	"""
	def __init__(self, file, line, column=None):
		self.file = file
		self.line = line
		self.column = column
	
	def __str__(self):
		str = "%s:%s" % (self.file, self.line)
		if self.column:
			str += ":%s" % self.column
		return str
	
	def __repr__(self):
		return str(self)


class ParseError(Exception):
	pass


class MetaParser(type):
	def __init__(cls, name, bases, nameSpace):
		if "rulesWithOpt" in nameSpace:
			for rule in cls.rulesWithOpt:
				cls.createOptRule(rule)
		
		if "rulesWithList" in nameSpace:
			for rule,sep in cls.rulesWithList.items():
				cls.createListRule(rule, sep)
		
	def createOptRule(cls, rulename):
		""" Create an `optional' rule.
		
		    Given a rule name, creates an optional ply.yacc rule for it.
		    The name of the optional rule is <rulename>_opt
		"""
		optname = rulename + "_opt"
		
		def optrule(self, p):
			p[0] = p[1]
		
		optrule.__doc__ = "%s : empty\n| %s" % (optname, rulename)
		optrule.__name__ = "p_%s" % optname
		setattr(cls, optrule.__name__, optrule)
	
	def createListRule(cls, rulename, sep = None):
		""" Create a list-of-rules rule.
		
		    Given a rule name, creates a list ply.yacc rule for it. The name of
		    the list rule is <rulename>_list. The new list is separated by `sep'
		    if this is provided, otherwise there is no separating token.
		"""
		sep = sep if sep is not None else ""
		
		def listrule(self, p):
			if len(p) == 2:
				p[0] = [p[1]]
			else:
				p[0] = p[1] + [p[len(p)-1]]
		listname = rulename + "_list"
		listrule.__doc__ = "%s : %s %s %s\n| %s" % (listname, listname, sep,
		                                            rulename, rulename)
		listrule.__name__ = listname = "p_%s" % listname
		setattr(cls, listname, listrule)


class RipleyParser(object, metaclass = MetaParser):
	def __init__(self, lexOptimize=False, lextab='lextab',
	                   yaccOptimize=False, yacctab='yacctab',
	                   yaccDebug=False):
		""" Create a new Parser.
		
		    Some arguments for controlling the debug/optimization
		    level of the parser are provided. The defaults are
		    tuned for release/performance mode.
		    The simple rules for using them are:
		    *) When releasing a stable parser, set to True
		
		    lexOptimize:
		        Set to False when you're modifying the lexer.
		        Otherwise, changes in the lexer won't be used, if
		        some lextab.py file exists.
		        When releasing with a stable lexer, set to True
		        to save the re-generation of the lexer table on
		        each run.
		
		    lextab:
		        Points to the lex table that's used for optimized
		        mode. Only if you're modifying the lexer and want
		        some tests to avoid re-generating the table, make
		        this point to a local lex table file (that's been
		        earlier generated with lex_optimize=True)
		
		    yaccOptimize:
		        Set to False when you're modifying the parser.
		        Otherwise, changes in the parser won't be used, if
		        some parsetab.py file exists.
		        When releasing with a stable parser, set to True
		        to save the re-generation of the parser table on
		        each run.
		
		    yacctab:
		        Points to the yacc table that's used for optimized
		        mode. Only if you're modifying the parser, make
		        this point to a local yacc table file
		
		    yaccDebug:
		        Generate a parser.out file that explains how yacc
		        built the parsing table from the grammar.
		"""
		self.curLex = RipleyLexer(errorFunc=self.lexErrorFunc)
		
		self.curLex.build(optimize=lexOptimize, lextab=lextab)
		
		self.tokens = self.curLex.tokens
		
		self.parser = yacc.yacc(module=self, start='base', debug=yaccDebug,
		                        optimize=yaccOptimize, tabmodule=yacctab)
	
	def parse(self, text, fileName='', debugLevel=0):
		""" Parses the IDL and returns an AST.
		
		    text:
		        A string containing the IDL source code
		
		    fileName:
		        Name of the file being parsed (for meaningful error messages)
		
		    debugLevel:
		        Debug level to yacc
		"""
		self.curLex.fileName = fileName
		self.curLex.resetLineNumber()
		return self.parser.parse(input=text, lexer=self.curLex,
		                         debug=debugLevel)
	
	def getCoord(self, lineno, column=None):
		""" Returns a coordinate for the given lex line.
		
		    Creates a `Coord' object with given details of the file, and
		    coordinates.
		"""
		return Coord(file=self.curLex.fileName, line=lineno, column=column)
	
	def lexErrorFunc(self, msg, line, column):
		coord = self.getCoord(line, column)
		raise ParseError("%s: %s" % (coord, msg))
	
	##
	# Parse unit specification
	##
	
	rulesWithOpt = ["params"]
	
	rulesWithList = {"interface" : None,
	                 "method" : None,
	                 "serviced" : None,
	                 "param" : "COMMA"}
	
	def p_error(self, p):
		# If error recovery is added here in the future, make sure
		# _get_yacc_lookahead_token still works!
		#
		if p:
			raise ParseError('before: %s @ %s' % (
			    p.value,
			    self.getCoord(p.lineno, column=self.curLex.findTokenColumn(p))))
		else:
			raise ParseError('At end of input')
	
	def p_empty(self, p):
		""" empty : """
		p[0] = None
	
	def p_base(self, p):
		""" base : interface_list
		         | empty
		"""
		p[0] = p[1]
		
	def p_interface(self, p):
		""" interface : service_def
		              | class_def
		              | function_def
		              | exception_def
		              | type_def
		"""
		p[0] = p[1]
	
	def p_function_def(self, p):
		""" function_def : ID params RARROW params
		                 | ID params
		"""
		if len(p) == 5:
			p[0] = FunctionEvalDef(name=p[1], params=p[2], returns=p[4])
		else:
			p[0] = FunctionNotifDef(name=p[1], params=p[2])
	
	def p_type_def(self, p):
		""" type_def : TYPE TYPEID
		"""
		p[0] = TypeDef(name=p[2])
	
	def p_exception_def(self, p):
		""" exception_def : EXCEPTION TYPEID params 
		"""
		p[0] = ExceptionDef(name=p[2], params=p[3])
	
	def p_params(self, p):
		""" params : LPAREN param_list RPAREN
		           | LPAREN RPAREN
		"""
		if len(p) == 3:
			p[0] = []
		else:
			p[0] = p[2]
	
	def p_param(self, p):
		""" param : ID COLON TYPEID
		          | TYPEID
		"""
		if len(p) == 4:
			p[0] = Parameter(type=p[3], name=p[1])
		else:
			p[0] = Parameter(type=p[1])
	
	def p_class_def(self, p):
		""" class_def : CLASS TYPEID LBRACE method_list RBRACE
		"""
		p[0] = ClassDef(name=p[2], methodList=p[4])
	
	def p_method(self, p):
		""" method : function_def
		"""
		p[0] = p[1]
	
	def p_service_def(self, p):
		""" service_def : SERVICE TYPEID LBRACE serviced_list RBRACE
		"""
		p[0] = ServiceDef(name=p[2], ifaceList=p[4])
	
	def p_serviced(self, p):
		""" serviced : thing_ref
		             | function_def
		"""
		p[0] = p[1]
	
	def p_thing_ref(self, p):
		""" thing_ref : ID
		              | TYPEID
		"""
		p[0] = NameReference(p[1])
