""" Module:  process.py
    Authors: 2015 - Trevor Hinkley (trevor@hinkley.email)
    License: MIT

    This file defines the processing code used for extracting an abstract
    intermediate representation from the abstract syntax tree. This AIR is
    then ready for compilation into the target code.
"""

# Local imports
from ast   import *
from scope import *

# Exports
__all__ = ["Processed"]

class Processed:
	def __init__(self, ast, typeBaseMap, AbstractCompiler, ObjectCompiler,
		               ExceptionCompiler):
		(abstract, classes, functions,
		 services, exceptions        ) = processRoot(ast, typeBaseMap,
		                                             AbstractCompiler,
		                                             ObjectCompiler,
		                                             ExceptionCompiler)
		self.abstract = abstract
		self.classes = classes
		self.functions = functions
		self.services = services
		self.exceptions = exceptions


def processRoot(ast, typeBaseMap, AbstractCompiler, ObjectCompiler,
	            ExceptionCompiler):
	rootScope = ParseScope(typeBaseMap = typeBaseMap)
	imported = []
	abstractTypes = []
	classTypes = []
	services = []
	functions = []
	exceptions = []
	
	for node in ast:
		if isinstance(node, TypeDef):
			newType = AbstractType(node.name, AbstractCompiler(node.name))
			rootScope.addType(newType)
			abstractTypes.append(newType)
		
		elif isinstance(node, ClassDef):
			newType = processClass(node.name, node.methodList, rootScope,
			                       ObjectCompiler)
			rootScope.addType(newType)
			classTypes.append(newType)
		
		elif isinstance(node, (FunctionNotifDef, FunctionEvalDef)):
			newFunction = functionHelper(node, scope)
			rootScope.addValue(newFunction)
			functions.append(newFunction)
		
		elif isinstance(node, ServiceDef):
			service, newFunctions = processService(node.name, node.ifaceList,
			                                       rootScope)
			services.append(service)
			functions += newFunctions
		
		elif isinstance(node, ExceptionDef):
			newException = processException(node.name, node.params, rootScope,
			                                ExceptionCompiler)
			rootScope.addType(newException)
			exceptions.append(newException)
		
		else:
			raise(Exception("Unexpected parse thing %s"%node))
	
	return abstractTypes, classTypes, functions, services, exceptions


def processService(name, interfaces, scope):
	functionList = []
	memberList = []
	for interface in interfaces:
		if isinstance(interface, (FunctionNotifDef,FunctionEvalDef)):
			newFunction = functionHelper(interface, scope)
			functionList.append(newFunction)
			memberList.append(newFunction)
		elif isinstance(interface, NameReference):
			if scope.hasType(interface.name):
				typeRef = scope.getType(interface.name)
				if not isinstance(typeRef, ClassType):
					raise(TypeError("Unexpected type reference %s", typeRef))
				memberList.append(typeRef)
			elif scope.hasValue(interface.name):
				valueRef = scope.getValue(interface.name)
				if not isinstance(valueRef, Function):
					raise(TypeError("Unexpected value reference %s", valueRef))
				memberList.append(valueRef)
		else:
			raise(TypeError("Unexpected parse thing %s"%interface))
	return ServiceType(name, memberList), functionList


def functionHelper(node, scope):
	if isinstance(node, FunctionNotifDef):
		return processNotification(node.name, node.params, scope)
	elif isinstance(node, FunctionEvalDef):
		return processEvaluation(node.name, node.params, node.returns, scope)
	else:
		raise(KeyError)


def processException(name, params, scope, ExceptionCompiler):
	paramList = processParList(params, scope)
	
	return ExceptionType(name, ExceptionCompiler(name), paramList)


def processClass(name, methods, scope, ObjectCompiler):
	methodList = []
	
	for method in methods:
		methodList.append(functionHelper(method, scope))
	
	return ClassType(name, ObjectCompiler(name), methodList)


def processEvaluation(name, params, returns, scope):
	paramList = processParList(params, scope)
	returnList = processParList(returns, scope)
	
	return Evaluation(name, paramList, returnList)


def processNotification(name, params, scope):
	paramList = processParList(params, scope)
	
	return Notification(name, paramList)


def processParList(params, scope):
	paramList = []
	for param in params:
		if param.name is None:
			name = "P%d"%len(paramList)
		else:
			name = param.name
		if not scope.hasType(param.type):
			raise(Exception("Type %s was not recognized"%param.type))
		parType = scope.getType(param.type)
		paramList.append((name, parType))
	return paramList

