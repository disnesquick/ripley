/**
 * @file   serialize.hpp
 * @author Trevor Hinkley
 * @date   14 July 2015
 * @brief  Header file for Ripley serialization functions.
 */

#ifndef RIPLEY_SERIALIZE_HPP
#define RIPLEY_SERIALIZE_HPP

#include <iostream>
#include <cstdint>
#include <vector>
#include <map>
#include <memory>



/** Base class for serial identifiers.
 *  
 *  This is the base clase, from which all objects with a unique ID derive.
 *  Examples include message IDs, object IDs, connection IDs and bus IDs.
 */
class SerialID {
	friend class SerialIDCompare;

public:
	SerialID(unsigned int val);
	
	void writeTo(std::ostream& outStream) const;
	inline static SerialID readFrom(std::istream& inStream) {
		return SerialID(inStream);
	}
	SerialID(std::istream& inStream);
	
	bool operator==(const SerialID& rhs) {
		return value == rhs.value;
	}
	
	inline operator unsigned int() {
		return value;
	}
protected:
	unsigned int value;
	std::vector<uint8_t> repr;
};

struct SerialIDCompare {
	bool operator() (const SerialID& lhs, const SerialID& rhs) {
		return lhs.value < rhs.value;
	}
};

template <typename ValueType>
using SerialIDMap = std::map<unsigned int, ValueType>;

template <typename ValueType>
using FullSerialIDMap = std::map<SerialID, ValueType, SerialIDCompare>;

class ConnectionID : public SerialID {
	using SerialID::SerialID;
};




class BusID : public ConnectionID {
	using SerialID::SerialID;
};


class ObjectID: public SerialID {
	using SerialID::SerialID;
};


class Reference {
	friend class ReferenceCompare;

public:
	Reference (ConnectionID& cID, unsigned int oID) :
		connectionID(cID), objectID(oID) {};
	
	Reference (ConnectionID& cID, ObjectID& oID) :
		connectionID(cID), objectID(oID) {};
	
	void writeTo(std::ostream& outStream) const;
	
	bool operator==(const Reference& rhs) {
		return connectionID == rhs.connectionID && objectID == rhs.objectID;
	}
	ConnectionID& connectionID;
	ObjectID objectID;
};


struct ReferenceCompare {
	bool operator() (const Reference& lhs, const Reference& rhs) {
		return (  SerialIDCompare()(lhs.connectionID, rhs.connectionID)
		       || ( !SerialIDCompare()(rhs.connectionID, lhs.connectionID)
		          && SerialIDCompare()(lhs.objectID, rhs.objectID)));
	}
};

template <typename ValueType>
using ReferenceMap = std::map<Reference, ValueType, ReferenceCompare>;



class UnicodeString {
public:
	typedef std::wstring RawType;
	
	void writeTo(std::ostream& outStream) const;
	inline static SerialID readFrom(std::istream& inStream) {
		return SerialID(inStream);
	}

};


class Route;

/** Base class for objects that can be transmitted by reference.
 * 
 *  This is the root class for all of those derived data-types that can be
 *  sent across the gateway "by-reference". Note that these objects do not
 *  have to be single-dispatch 'class' objects just objects that can be
 *  kept locally but referenced remotely.
 */
class PassByReference : public std::enable_shared_from_this<PassByReference> {
public:
	typedef std::shared_ptr<PassByReference> SharedPtr;
	virtual Reference* getReference() {return nullptr;};
};

/** Base class for proxy objects.
 *  
 *  Proxy objects are bound to a particular route with an identifying
 *  reference, which is uesd to recognition on reception of an incoming
 *  identification. the ObjectProxy class here is implemented as a mix-in.
 */ 
template <typename DType>
class ObjectProxy : public DType{
	friend class Connection;

public:
	ObjectProxy(Route& destination, Reference& reference) :
		destination(destination), reference(reference) {};
	virtual Reference* getReference() final {return &reference;};

private:
	Route& destination;
	Reference reference;

};
#endif
