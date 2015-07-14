""" Module:  lexer.py
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file defines a lexer for the Ripley code generator, using the ply
    library.
"""

import sys
import ply.lex as lex
import re


class RipleyLexer(object):
	""" A lexer for the Ripley interface description language.
	
	    This class defines the `ply' lexer for the Ripley IDL.
	"""
	def __init__(self, errorFunc):
		""" Create a new Lexer.
		
		    errorFunc:
		        An error function. Will be called with an error
		        message, line and column as arguments, in case of
		        an error during lexing.
		"""
		self.errorFunc = errorFunc
		self.fileName = ''
		
		# Keeps track of the last token returned from self.token()
		self.lastToken = None
	
	def build(self, **kwargs):
		""" Builds the lexer from the specification. 
		
		    Must be called after the lexer object is created.  This method
		    exists separately, because the PLY manual warns against calling
		    lex.lex inside __init__.
		"""
		self.lexer = lex.lex(object=self, **kwargs)
	
	def resetLineNumber(self):
		""" Resets the internal line number counter of the lexer.
		"""
		self.lexer.lineno = 1
	
	def input(self, text):
		""" Pass-through to inner lexer.
		"""
		self.lexer.input(text)
	
	def token(self):
		""" Pass-through to inner lexer and store `lastToken'.
		"""
		self.lastToken = self.lexer.token()
		return self.lastToken
	
	def findTokenColumn(self, token):
		""" Find the column of the token in its line.
		"""
		last_cr = self.lexer.lexdata.rfind('\n', 0, token.lexpos)
		return token.lexpos - last_cr
	
	##
	# Token specification.
	##
	
	keywords = ("CLASS","SERVICE","EXCEPTION", "TYPE")
	keywordMap = {}
	for r in keywords:
		keywordMap[r.lower()] = r
	
	tokens = keywords + (
	    'ID', 'TYPEID',
	    'LPAREN', 'RPAREN',
	    'LBRACE', 'RBRACE',
	    'LARROW', 'RARROW',
	    'COMMA', 'COLON', 'SEMI'
	)
	
	# Completely ignored characters
	t_ignore           = ' \t\x0c'
	
	# Delimeters
	t_LPAREN = r'\('
	t_RPAREN = r'\)'
	t_LBRACE = r'\{'
	t_RBRACE = r'\}'
	t_COMMA  = r','
	t_SEMI   = r';'
	t_COLON  = r':'
	t_LARROW = r'<-'
	t_RARROW = r'->'
	
	# Identifier
	def t_ID(self, t):
		r'[a-z_][\w_]*'
		t.type = self.keywordMap.get(t.value,"ID")
		return t
	
	# Identifier
	def t_TYPEID(self, t):
		r'[A-Z][\w_]*'
		t.type = self.keywordMap.get(t.value,"TYPEID")
		return t
	
	# Comment
	def t_comment(self, t):
		r' /\*(.|\n)*?\*/'
		t.lineno += t.value.count('\n')
	
	def t_newline(self, t):
		r'\n'
		t.lineno += 1
	
	# Error
	def t_error(self, t):
		print ("Illegal character %s" % repr(t.value[0]))
		t.lexer.skip(1)
