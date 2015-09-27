/**
 * @file   route.hpp
 * @author Trevor Hinkley
 * @date   27 September 2015
 * @brief  Header file for Ripley Route Class.
 */

#ifndef RIPLEY_ROUTE_HPP
#define RIPLEY_ROUTE_HPP
/** A Route reifies a path to a Connection on a Bus.
 * 
 *  A Route object defines a one-directional path from one connection,
 *  through the bus to a corresponding route (which points to this
 *  connection) on a separate connection. This enables reply-paths to work.
 *  Thus, when a Route is created, it must be during some process which
 *  creates a corresponding Route on the other Bus.  A Route is therefore
 *  always created via an OpenRoute object.
 */

class Route {
private:
	Connection& origin; /// The originating connection of this route.
	Transport& transport; /// The transport to use for this route.
	
public:
	Route(Connection& connection, Transport& transport) :
		origin(connection), transport(transport);
	std::ostream getOutputBuffer();
};

void Route::setDestination
#endif // RIPLEY_ROUTE_HPP
