/**
 * @file   connection.hpp
 * @author Trevor Hinkley
 * @date   14 July 2015
 * @brief  Header file for Ripley Connection class.
 */

#ifndef RIPLEY_CONNECTION_HPP
#define RIPLEY_CONNECTION_HPP


#include "serialize.hpp"
#include <memory>

/** This class reifies an encapsulated process on a Bus.
 * 
 *  This class handles the mapping of object IDs to and from objects. It
 *  also handles the exposure of objects through transverse identifiers.
 *  Finally it contains the processing methods for handling incoming binary
 *  message streams and the calling of appropriate local methods
 */

class Connection {
public:
	Connection(ConnectionID neonateID) :
		objectCount(0), connectionID(neonateID) {};
	
	Connection(unsigned int neonateID) :
		objectCount(0), connectionID(neonateID) {};
	
	/// @brief Deserializes and type-checked a single PassByReference object.
	template <typename E>
	std::shared_ptr<E> deserializeObject(std::istream& inStream);
	
	/// @brief Serializes a PassByReference object.
	void serializeObject(PassByReference& obj, std::ostream& outStream);

private:
	/// @brief Creates a new ObjectID with a unique value.
	ObjectID generateObjectID();
	
	/// @brief Maps an incoming object reference to a C++ object.
	template <class E, typename ProxyClass = typename E::ProxyClass>
	std::shared_ptr<E> referenceToObject(ConnectionID& targetID,
	                                     ObjectID& objectID);
	
	/// @brief Obtains a reference identifier for an object.
	Reference& objectToReference(PassByReference& obj);
	
	// Member variables
	/// Map from ObjectIDs to associated shared objects.
	SerialIDMap<PassByReference::SharedPtr> objectIDObject;
	/// Map from objects to associated ObjectIDs.
	std::map<PassByReference*, Reference> objectReference;
	/// Map from ConnectionIDs to associated Routes
	FullSerialIDMap<Route*> proxyTokens;
	/// int counter to allow for unique IDs on ObjectIDs.
	int objectCount;
	/// Unique ConnectionID associated with this Connection.
	ConnectionID connectionID;
};

#endif
