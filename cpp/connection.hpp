#include "serialize.hpp"


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
		objectCount(0), connectionID(neonateID);
	
	template <typename Expected>
	Expected deserializeObject(std::istream& inStream);
	
private:
	ObjectID generateObjectID();
	
	// Member variables
	SerialIDMap<PassByReference*> objectIDToObject;
	SerialIDMap<Route*> proxyTokens;
	std::map<PassByReference*, Reference> objectToReference;
	int objectCount;
	
	ConnectionID connectionID;
};

/** Deserializes and type-checked a single PassByReference object.
 * 
 *  This function deserializes a reference from inStream and matches
 *  it to an object in the local cache (or creates a proxy object).
 *  Type checking on local objects is performed to prevent spoofing.
 */ 
template <typename Expected>
Expected* Connection::deserializeObject(std::istream& inStream) {
	ConnectionID connectionID = ConnectionID::readFrom(inStream);
	ObjectID objectID = ObjectID::readFrom(inStream);
	return referenceToObject<Expected>(connectionID, objectID);
}

/** Generates an object ID in the form of a SerialID.
 *
 *  Referencess are transfered in the form of a connection-specific
 *  unique identifier plus an identifier for the connection itself.
 *  However, this connectionID is handled elsewhere.
 */
ObjectID Connection::generateObjectID() {
	return ObjectID(objectCount++);
}

/** Obtains a reference identifier for an object.
 *
 *  If the object has been shared previously then the previous reference
 *  is returned, otherwise a reference is generated and marked against
 *  the object.  The connection ID is added for local objects to create
 *  a complete reference.
 */
Reference& Connection::objectToReference(PassByReference& obj) {
	Reference* tmp;
	if ((tmp = obj.getReference()) != nullptr)
		return *tmp;
	try {
		return objectToReference.at(obj);
	} catch (std::range_error e) {
		ObjectID objectID = generateObjectID();
		objectIDToObject[objectID] = &obj;
		return (objectToReference[&obj] = Reference(connectionID, objectID));
	}
}
/** Maps an incoming object reference to a C++ object.
 *
 *  Local objects will be mapped to their local C++ object whereas
 *  remote objects will be wrapped in an object proxy.
 */
template <typename Expected>
Expected* Connection::referenceToObject(ConnectionID& targetID,
                                        ObjectID& objectID) {
	if (targetID == connectionID) {
		try {
			Expected* tmp;
			tmp = objectIDToObject.at(ref.objectID);
			return &dynamic_cast<Expected&>(*tmp);
		} catch (std::out_of_range e) {
			throw UnknownObjectIDError(ref.objectDI);
		} catch (std::bad_cast e)
			throw TypeMismatchError(typeid(Expected).name(),
			                        typeid(ref).name());
	} else {
		decltype(proxyTokens)::iterator it;
		it = proxyTokens.find(targetID);
		if (it == proxyTokens.end()) 
			throw UnknownConnectionIDError(targetID);
		return Expected::ProxyClass(it->second,
		                            Reference(it->first, objectID));
	}
}

