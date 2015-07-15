#include <iostream>
#include <cassert>
#include <memory>
#include <string>
#include "stubs.hpp"
#include "../serialize.hpp"
#include <sstream>


#define CATCH_CONFIG_MAIN
#include "catch.hpp"

class TestInterface1 : public PassByReference{
public:
	
	virtual int add(int a, int b)=0;
};

class TestImplementation1 : public TestInterface1 {
public:
	virtual int add(int a, int b) override {return a + b;}
};

class TestProxy1 : public ObjectProxy<TestInterface1> {
public:
	using ObjectProxy::ObjectProxy;
	virtual int add(int a, int b) override {return a + b + 1;}
};

class TestInterface2: public PassByReference{
};



TEST_CASE("SerialID objects can be manipulated", "[SerialID]") {
	SerialID sid(0xFFFF);
	std::string matchString("\xFF\xFF\x03");
	
	SECTION("SerialID can be serialized correctly") {
		std::ostringstream output;
		sid.writeTo(output);
		REQUIRE(output.str() == matchString);
	}
	
	SECTION("SerialID can be deserialized correctly") {
		std::ostringstream output;
		sid.writeTo(output);
		std::istringstream input(output.str());
		
		SerialID mid = SerialID::readFrom(input);
		std::ostringstream output2;
		mid.writeTo(output2);
		
		REQUIRE(output2.str() == matchString);
	}
	
	SECTION("SerialIDMap stores and retrieves") {
		SerialIDMap<int> map;
		SerialID sID1(0x03);
		SerialID sID2(0x03);
		SerialID sID3(0x04);
		
		map[sID1] = 5;
		
		REQUIRE(map.at(sID2) == 5);
		REQUIRE_THROWS(map.at(sID3));
	}
	Route routeStub;
	ConnectionID cID(0x01);
	ObjectID oID1(0x03);
	ObjectID oID2(0x03);
	ObjectID oID3(0x04);
	Reference rID1(cID, oID1);
	Reference rID2(cID, oID2);
	Reference rID3(cID, oID3);
	
	SECTION("Map of objectIDs stores and retrieves") {
		SerialIDMap<int> map;
		
		map[oID1] = 5;
		
		REQUIRE(map.at(oID2) == 5);
		REQUIRE_THROWS(map.at(oID3));
	}
	
	SECTION("ReferenceMap casting of PassByReference objects") {
		SerialIDMap<PassByReference*> map;
		
		TestImplementation1 a;
		
		map[oID1] = &a;
		
		REQUIRE_NOTHROW(dynamic_cast<TestInterface1&>(*map.at(oID1)));
		REQUIRE_THROWS(dynamic_cast<TestInterface2&>(*map.at(oID1)));
	}
	
	SECTION("ReferenceMap casting of shared_ptr PassByReference") {
		SerialIDMap<PassByReference::SharedPtr> map;
		
		TestImplementation1* a = new TestImplementation1;
		
		map[oID1] = PassByReference::SharedPtr(a);
		
		REQUIRE(std::dynamic_pointer_cast<TestInterface2>(map.at(oID1)) == nullptr);
		REQUIRE(std::dynamic_pointer_cast<TestInterface1>(map.at(oID1)) != nullptr);
	}
	
	
	SECTION("Differentiation between Proxy and Implementation") {
		SerialIDMap<PassByReference*> map;
		
		TestImplementation1 impl;
		TestProxy1 proxy(routeStub, rID1);
		
		map[oID1] = &impl;
		map[oID3] = &proxy;
		
		TestInterface1& ifaceI = dynamic_cast<TestInterface1&>(*map.at(oID1));
		TestInterface1& ifaceP = dynamic_cast<TestInterface1&>(*map.at(oID3));
		REQUIRE(ifaceI.getReference() == nullptr);
		REQUIRE(*ifaceP.getReference() == rID1);
		
	}
}

