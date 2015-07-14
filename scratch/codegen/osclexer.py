# ----------------------------------------------------------------------
# clex.py
#
# A lexer for ANSI C.
# ----------------------------------------------------------------------

import sys
import ply.lex as lex
import re


class OSCLexer(object):
	""" A lexer for the C language. After building it, set the
	    input text with input(), and call token() to get new
	    tokens.
	
	    The public attribute filename can be set to an initial
	    filaneme, but the lexer will update it upon #line
	    directives.
	"""
	def __init__(self, error_func):
		""" Create a new Lexer.
		
		    error_func:
		        An error function. Will be called with an error
		        message, line and column as arguments, in case of
		        an error during lexing.
		
		    on_lbrace_func, on_rbrace_func:
		        Called when an LBRACE or RBRACE is encountered
		        (likely to push/pop type_lookup_func's scope)
		
		    type_lookup_func:
		        A type lookup function. Given a string, it must
		        return True IFF this string is a name of a type
		        that was defined with a typedef earlier.
		"""
		self.error_func = error_func
		self.filename = ''
		
		# Keeps track of the last token returned from self.token()
		self.last_token = None
		
		# Allow either "# line" or "# <num>" to support GCC's
		# cpp output
		#
		self.line_pattern = re.compile('([ \t]*line\W)|([ \t]*\d+)')
		self.pragma_pattern = re.compile('[ \t]*pragma\W')

	def build(self, **kwargs):
		""" Builds the lexer from the specification. Must be
		    called after the lexer object is created.
		
		    This method exists separately, because the PLY
		    manual warns against calling lex.lex inside
		    __init__
		"""
		self.lexer = lex.lex(object=self, **kwargs)
    
    	# Reserved words
	reserved = (
            'BOOL',
            'TIMETAG',
	    'INT',
	    'LONG',
	    'FLOAT',
	    'DOUBLE',
	    'CHAR',
	    'STRING',
	    'BLOB'

	)
    
	tokens = reserved + (
	    # Literals (identifier, integer constant, float constant, string constant, char const)
	    'ID', 
	    #'ICONST', 'FCONST', 'SCONST', 'CCONST',
	    'UNITS',
	    # Operators (+,-,*,/,%,|,&,~,^,<<,>>, ||, &&, !, <, <=, >, >=, ==, !=)
	    'DIVIDE',
	    'LPAREN', 'RPAREN',
	    #'LBRACKET', 'RBRACKET',
	    #'LBRACE', 'RBRACE',
	    'COMMA'
	
	)

	# Completely ignored characters
	t_ignore           = ' \t\x0c'

	# Newlines
	def t_NEWLINE(self,t):
	    r'\n+'
	    t.lexer.lineno += t.value.count("\n")
	    
	# Operators
	t_PLUS             = r'\+'
	t_MINUS            = r'-'
	t_TIMES            = r'\*'
	t_DIVIDE           = r'/'
	t_MOD              = r'%'
	t_OR               = r'\|'
	t_AND              = r'&'
	t_NOT              = r'~'
	t_XOR              = r'\^'
	t_LSHIFT           = r'<<'
	t_RSHIFT           = r'>>'
	t_LOR              = r'\|\|'
	t_LAND             = r'&&'
	t_LNOT             = r'!'
	t_LT               = r'<'
	t_GT               = r'>'
	t_LE               = r'<='
	t_GE               = r'>='
	t_EQ               = r'=='
	t_NE               = r'!='

	# Assignment operators
	t_EQUALS           = r'='
	t_TIMESEQUAL       = r'\*='
	t_DIVEQUAL         = r'/='
	t_MODEQUAL         = r'%='
	t_PLUSEQUAL        = r'\+='
	t_MINUSEQUAL       = r'-='
	t_LSHIFTEQUAL      = r'<<='
	t_RSHIFTEQUAL      = r'>>='
	t_ANDEQUAL         = r'&='
	t_OREQUAL          = r'\|='
	t_XOREQUAL         = r'^='
	
	# Increment/decrement
	t_PLUSPLUS         = r'\+\+'
	t_MINUSMINUS       = r'--'
	
	# ->
	t_ARROW            = r'->'
	
	# ?
	t_CONDOP           = r'\?'
	
	# Delimeters
	t_LPAREN           = r'\('
	t_RPAREN           = r'\)'
	t_LBRACKET         = r'\['
	t_RBRACKET         = r'\]'
	t_LBRACE           = r'\{'
	t_RBRACE           = r'\}'
	t_COMMA            = r','
	t_PERIOD           = r'\.'
	t_SEMI             = r';'
	t_COLON            = r':'
	t_ELLIPSIS         = r'\.\.\.'
	
	# Identifiers and reserved words
	
	reserved_map = {}
	for r in reserved:
		reserved_map[r.lower()] = r
	
	# Integer literal
	t_ICONST = r'\d+([uU]|[lL]|[uU][lL]|[lL][uU])?'
	
	# Floating literal
	t_FCONST = r'((\d+)(\.\d+)(e(\+|-)?(\d+))? | (\d+)e(\+|-)?(\d+))([lL]|[fF])?'
	
	# String literal
	t_SCONST = r'\"([^\\\n]|(\\.))*?\"'
	
	# Character constant 'c' or L'c'
	t_CCONST = r'(L)?\'([^\\\n]|(\\.))*?\''

	t_UNITS = r'((\w+\d+)+|(\w+\d+)*\\/(\w+\d+)+)'

	def t_ID(self, t):
		r'[A-Za-z_][\w_]*'
		t.type = self.reserved_map.get(t.value,"ID")
		return t

	def t_comment(self, t):
		r' /\*(.|\n)*?\*/'
		t.lineno += t.value.count('\n')
	
	def t_preprocessor(self, t):
		r'\#(.)*?\n'
		t.lineno += 1
	    
	def t_error(self, t):
		print ("Illegal character %s" % repr(t.value[0]))
		t.lexer.skip(1)
	    

	def resetLineNumber(self):
		""" Resets the internal line number counter of the lexer.
		"""
		self.lexer.lineno = 1
	
	def input(self, text):
		self.lexer.input(text)
	
	def token(self):
		self.lastToken = self.lexer.token()
		return self.lastToken


	def findTokenColumn(self, token):
		""" Find the column of the token in its line.
		"""
		last_cr = self.lexer.lexdata.rfind('\n', 0, token.lexpos)
		return token.lexpos - last_cr
		
