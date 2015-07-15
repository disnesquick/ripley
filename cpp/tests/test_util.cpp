#include <iostream>
#include <cassert>
#include <string>
#include "../util.hpp"
#include <sstream>


#define CATCH_CONFIG_MAIN
#include "catch.hpp"

void fillMemory(int a[]) {
	for (int i=0; i<0x100000; i++) {
		a[i] = 1;
	}
}

template <typename T>
SmartPtr<T> getVisitorPointer(T a) {
	return VisitorPtr<T>(a);
}
template <typename T>
SmartPtr<T> getOwnerPointer(T a) {
	return OwnerPtr<T>(a);
}


TEST_CASE("Testing SmartPtr behaviour", "[SmartPtr]") {

	SECTION("Creation of a VisitorPtr") {
		int a = 5;
		VisitorPtr<int> b(a);
		*b = 6;
		
		REQUIRE(a == 6);
	}
	SECTION("Test deletion of visitor") {
		int *a = new int[0x100000];
		{
			auto b = getVisitorPointer(a);
		}
		
		REQUIRE_NOTHROW(fillMemory(a));
	}
	SECTION("Test deletion of owner") {
		int *a = new int[0x100000];
		{
			auto b = getOwnerPointer(a);
			REQUIRE_NOTHROW(fillMemory(a));
		}
		
	}
}

