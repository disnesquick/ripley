#include "errors.hpp"
#include "serialize.hpp"
#include "connection.hpp"
#include <exception>
#include <string>

/** Referencess are transfered in the form of a connection-specific
 *  unique identifier plus an identifier for the connection itself.
 *  However, this connectionID is handled elsewhere.
 */
ObjectID Connection::generateObjectID() {
	return ObjectID(objectCount++);
}


/** This function deserializes a reference from inStream and matches
 *  it to an object in the local cache (or creates a proxy object).
 *  Type checking on local objects is performed to prevent spoofing.
 */ 
template <typename E>
std::shared_ptr<E> Connection::deserializeObject(std::istream& inStream) {
	ConnectionID connectionID = ConnectionID::readFrom(inStream);
	ObjectID objectID = ObjectID::readFrom(inStream);
	
	return referenceToObject<E>(connectionID, objectID);
}


/** Local objects will be mapped to their local C++ object whereas
 *  remote objects will be wrapped in an object proxy.
 */
template <class E, typename ProxyClass>
std::shared_ptr<E> Connection::referenceToObject(ConnectionID& targetID,
                                                    ObjectID& objectID) {
	
	if (targetID == connectionID) {
		try {
			std::shared_ptr<PassByReference> tmpBase;
			tmpBase = objectIDObject.at(objectID);
			std::shared_ptr<E> tmp = std::dynamic_pointer_cast<E>(tmpBase);
			if (tmp == nullptr)
				throw TypeMismatchError(typeid(E).name(),
				                        typeid(*tmpBase).name());
			else
				return tmp;
		} catch (std::out_of_range e) {
			throw UnknownObjectIDError(objectID);
		}
	} else {
		decltype(proxyTokens)::iterator it;
		it = proxyTokens.find(targetID);
		if (it == proxyTokens.end()) 
			throw UnknownConnectionIDError(targetID);
		
		return std::shared_ptr<E>(
		  new ProxyClass(it->second,
		    Reference(it->first, objectID)));
	}

}

/** This function obtains a reference to the supplied object and writes
 *  it to the outputStream. No type checking is performed.
 */
void Connection::serializeObject(PassByReference& obj, std::ostream& outStream) {
	Reference& ref = objectToReference(obj);
	ref.writeTo(outStream);
}


/** If the object has been shared previously then the previous reference
 *  is returned, otherwise a reference is generated and marked against
 *  the object.  The connection ID is added for local objects to create
 *  a complete reference.
 */
Reference& Connection::objectToReference(PassByReference& obj) {
	decltype(objectReference)::iterator ft;
	Reference* tmp;
	if ((tmp = obj.getReference()) != nullptr)
		return *tmp;
	
	ft = objectReference.find(&obj);
	if (ft == objectReference.end()) {
		ObjectID objectID = generateObjectID();
		objectIDObject[objectID] = PassByReference::SharedPtr(&obj);
		
		return objectReference.insert(
		  std::pair<PassByReference*, Reference>(
		    &obj, Reference(connectionID, objectID))).first->second;
	} else
		return ft->second;
}


