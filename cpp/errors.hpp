/**
 * @file   errors.hpp
 * @author Trevor Hinkley
 * @date   14 July 2015
 * @brief  Header file for Ripley exception definitions.
 */

#ifndef RIPLEY_ERRORS_HPP
#define RIPLEY_ERRORS_HPP

#include <exception>
#include <string>
#include "serialize.hpp"

class TypeMismatchError : public std::exception {
public:
	TypeMismatchError(char castTo[], char castFrom[]) :
		castTo(castTo), castFrom(castFrom) {};

private:
	std::string castTo, castFrom;
};


class UnknownObjectIDError : public std::exception {
public:
	UnknownObjectIDError(ObjectID objectID) :
		objectID(objectID) {};
	
private:
	ObjectID objectID;
};


class UnknownConnectionIDError : public std::exception {
public:
	UnknownConnectionIDError(ConnectionID connectionID) :
		connectionID(connectionID) {};
	
private:
	ConnectionID connectionID;
};

#endif
