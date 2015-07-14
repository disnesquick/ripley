from ply import yacc

from osclexer import OSCLexer
from oscast import *


class Coord(object):
	""" Coordinates of a syntactic element. Consists of:
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
		if self.column: str += ":%s" % self.column
		return str


class ParseError(Exception):
	pass


class OSCParser(object):
	def __init__( self, lex_optimize=True, lextab='pycparser.lextab', yacc_optimize=True, yacctab='pycparser.yacctab', yacc_debug=False):
		""" Create a new CParser.
		
		    Some arguments for controlling the debug/optimization
		    level of the parser are provided. The defaults are
		    tuned for release/performance mode.
		    The simple rules for using them are:
		    *) When tweaking CParser/CLexer, set these to False
		    *) When releasing a stable parser, set to True
		
		    lex_optimize:
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
		
		    yacc_optimize:
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
		
		    yacc_debug:
		        Generate a parser.out file that explains how yacc
		        built the parsing table from the grammar.
		"""
		self.curLex = OSCLexer(
		    error_func=self.lexErrorFunc)
		
		self.curLex.build(
		    optimize=lex_optimize,
		    lextab=lextab)

		self.tokens = self.curLex.tokens
		
		rulesWithOpt = [

		]
		
		rulesWithList = {
		    'osc_unit':'DIVIDE',
		    'type_spec':'COMMA',
		    'def':None
		}




		for rule in rulesWithOpt:
			self.createOptRule(rule)
		
		for rule in rulesWithList:
			sep = rulesWithList[rule]
			self.createListRule(rule, sep)

		self.cparser = yacc.yacc(
		    module=self,
		    start='base',
		    debug=yacc_debug,
		    optimize=yacc_optimize,
		    tabmodule=yacctab)

	@classmethod
	def createOptRule(cls, rulename):
		""" Given a rule name, creates an optional ply.yacc rule
		    for it. The name of the optional rule is
		    <rulename>_opt
		"""
		optname = rulename + "_opt"
		
		def optrule(self, p):
			p[0] = p[1]
		
		optrule.__doc__ = "%s : empty\n| %s" % (optname, rulename)
		optrule.__name__ = "p_%s" % optname
		setattr(cls, optrule.__name__, optrule)

	@classmethod
	def createListRule(cls, rulename, sep = None):
		""" Given a rule name, creates a list ply.yacc rule
		    for it. The name of the list rule is
		    <rulename>_list
		"""
		
		sep = sep if sep is not None else ""

		def listrule(self, p):
			if len(p) == 2:
				p[0] = [p[1]]
			else:
				p[0] = p[1] + [p[len(p)-1]]
		listname = rulename + "_list"
		listrule.__doc__ = "%s : %s %s %s\n| %s" %(listname, listname, sep, rulename, rulename)
		listrule.__name__ = listname = "p_%s" % listname
		setattr(cls, listname, listrule)


	def parse(self, text, filename='', debuglevel=0):
		""" Parses C code and returns an AST.
		
		    text:
		        A string containing the C source code
		
		    filename:
		        Name of the file being parsed (for meaningful
		        error messages)
		
		    debuglevel:
		        Debug level to yacc
		"""
		self.curLex.filename = filename
		self.curLex.resetLineNumber()
		return self.cparser.parse(
		        input=text,
		        lexer=self.curLex,
		        debug=debuglevel)


	def getCoord(self, linenoP, column=None):
		lineno = linenoP.lineno
		return Coord(
		        file=self.curLex.filename,
		        line=lineno,
		        column=column)

	def lexErrorFunc(self, msg, line, column):
		coord = self.getCoord(line, column)
		raise ParseError("%s: %s" % (coord, msg))


	def p_error(self, p):
		# If error recovery is added here in the future, make sure
		# _get_yacc_lookahead_token still works!
		#
		if p:
			raise ParseError('before: %s @ %s' % (
			    p.value,
			    self.getCoord(p, column=self.curLex.findTokenColumn(p))))
		else:
			raise ParseError('At end of input')


	def p_empty(self, p):
		'empty : '
		p[0] = None

	def p_osc_address(self, p):
		""" osc_address : DIVIDE osc_unit_list
		"""
		p[0] = OSCAddress(p[2], coord = self.getCoord(p))

	def p_osc_unit(self, p):
		""" osc_unit : ID
		"""
		p[0] = p[1]

	def p_base(self, p):
		"""base : def_list
		        | empty
		"""
		p[0] = p[1]

	def p_def(self, p):
		"""def   : osc_address ID type_spec_list 
		         | osc_address ID
		"""
		if p[1] is None:
			p[0] = []
		elif len(p) == 4:
			p[0] = OSCDefinition(p[1], p[2], p[3])
		else:
			p[0] = OSCDefinition(p[1], p[2], [])

	def p_basic_type(self, p):
		""" basic_type : BOOL
		               | CHAR
		               | INT
		               | LONG
		               | FLOAT
		               | DOUBLE
		               | STRING
		               | BLOB
		               | TIMETAG
		"""
		p[0] = BasicType(p[1])

	def p_type_spec(self, p):
		""" type_spec : basic_type
		              | basic_type LPAREN UNITS RPAREN
		"""
		if len(p) == 2:
			p[0] = p[1]
		else:
			p[0] = TypeWithUnits(p[1].typeDef, p[3])

