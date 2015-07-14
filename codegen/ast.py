""" Module:  ast.py
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file defines the various nodes that can be extracted into the final
    parsed Abstract Syntax Tree.
"""

class Parameter:
	def __init__(self, type, name=None):
		self.type = type
		self.name = name


class FunctionNotifDef:
	def __init__(self, name, params):
		self.name = name
		self.params = params


class FunctionEvalDef:
	def __init__(self, name, params, returns):
		self.name = name
		self.params = params
		self.returns = returns


class ClassDef:
	def __init__(self, name, methodList):
		self.name = name
		self.methodList = methodList


class ExceptionDef:
	def __init__(self, name, params):
		self.name = name
		self.params = params


class NameReference:
	def __init__(self, name):
		self.name = name


class ServiceDef:
	def __init__(self, name, ifaceList):
		self.name = name
		self.ifaceList = ifaceList


class TypeDef:
	def __init__(self, name):
		self.name = name
