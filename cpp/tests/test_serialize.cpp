#include <iostream>
#include <cassert>
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
	Reference rID1(cID, 0x03);
	Reference rID2(cID, 0x03);
	Reference rID3(cID, 0x04);
	
	SECTION("ReferenceMap stores and retrieves") {
		ReferenceMap<int> map;
		
		map[rID1] = 5;
		
		REQUIRE(map.at(rID2) == 5);
		REQUIRE_THROWS(map.at(rID3));
	}
	
	SECTION("ReferenceMap casting of PassByReference objects") {
		ReferenceMap<PassByReference*> map;
		
		TestImplementation1 a;
		
		map[rID1] = &a;
		
		REQUIRE_NOTHROW(dynamic_cast<TestInterface1&>(*map.at(rID1)));
		REQUIRE_THROWS(dynamic_cast<TestInterface2&>(*map.at(rID1)));
	}
	
	SECTION("Differentiation between Proxy and Implementation") {
		ReferenceMap<PassByReference*> map;
		
		TestImplementation1 impl;
		TestProxy1 proxy(routeStub, rID1);
		
		map[rID1] = &impl;
		map[rID3] = &proxy;
		
		TestInterface1& ifaceI = dynamic_cast<TestInterface1&>(*map.at(rID1));
		TestInterface1& ifaceP = dynamic_cast<TestInterface1&>(*map.at(rID3));
		REQUIRE(ifaceI.getReference() == nullptr);
		REQUIRE(*ifaceP.getReference() == rID1);
		
	}
}

