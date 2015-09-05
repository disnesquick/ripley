#include <iostream>
#include <cassert>
#include <string>
#include "../connection.hpp"
#include <sstream>


#define CATCH_CONFIG_MAIN
#include "catch.hpp"


class TestInterface : public PassByReference{
public:
	
	virtual int add(int a, int b)=0;
};

class TestImplementation : public TestInterface {
public:
	virtual int add(int a, int b) override {return a + b;}
};

class TestProxy : public ObjectProxy<TestInterface> {
public:
	using ObjectProxy::ObjectProxy;
	virtual int add(int a, int b) override {return a + b + 1;}
};

TEST_CASE("Creation of a Connection", "[Connection]") {
	
	SECTION("Creation of a Connection") {
		Connection cxn(3);
	}
	
	SECTION("Serializing a local object across a connection") {
		Connection cxn(3);
		std::ostringstream output;
		TestImplementation* impl = new TestImplementation;;
		
		REQUIRE_NOTHROW(cxn.serializeObject(*impl, output));
	}

	SECTION("Deserializing a local object from a connection") {
		Connection cxn(3);
		std::ostringstream output;
		TestImplementation* impl = new TestImplementation;
		cxn.serializeObject(*impl, output);
		std::istringstream input(output.str())
		TestImplementation *test = cxn.deserializeObject(input);
		require(test == impl);
	}
}

