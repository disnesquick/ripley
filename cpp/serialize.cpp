#include <algorithm>
#include "serialize.hpp"

#define MAX_ID_LENGTH ((6+sizeof(int)*8)/7)

SerialID::SerialID(unsigned int val) : 
	value(val) {
	uint8_t buffer[MAX_ID_LENGTH];
	int bufSize = 0;
	
	// Read the SerialiD into the temp buffer
	while (val & 0x80) {
		buffer[bufSize] = (val & 0x7F | 0x80);
		val >>= 7;
		bufSize++;
	}
	
	// Copy the SerialID from the temp buffer into the object's vector
	buffer[bufSize++] = val;
	repr.resize(bufSize);
	std::copy(buffer, buffer + bufSize, repr.begin());
}

SerialID::SerialID(std::istream& iHandle) : 
	value(0) {
	uint8_t buffer[MAX_ID_LENGTH];
	uint8_t curVal = 0x80;
	int shift = 0;
	int bufSize = 0;
	
	// Read the SerialiD into the temp buffer
	while (curVal & 0x80) {
		if (bufSize == MAX_ID_LENGTH)
			throw new std::length_error("SerialID from stream was too long");
		buffer[bufSize++] = curVal = iHandle.get();
		value |= static_cast<unsigned int>(curVal) << shift;
		shift += 7;
	}
	
	// Copy the SerialID from the temp buffer into the object's vector
	repr.resize(bufSize);
	std::copy(buffer, buffer + bufSize, repr.begin());
}

void SerialID::writeTo(std::ostream& outStream) const {
	std::copy(repr.begin(), repr.end(),
	          std::ostreambuf_iterator<char>(outStream));
}


void Reference::writeTo(std::ostream& outStream) const {
	connectionID.writeTo(outStream);
	objectID.writeTo(outStream);
}
