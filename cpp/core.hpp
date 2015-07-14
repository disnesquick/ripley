#include <ripley/service>
class TransportServer : public PassByReference {
protected:
	virtual void __abstractClassKludge() override {};
};

class ProspectiveRoute : public PassByReference {
protected:
	virtual void __abstractClassKludge() override {};
};

class OpenTransportProxy;

class OpenTransport : public PassByReference {
public:
	typedef OpenTransportProxy ProxyClass;
	virtual void accept(TransportServer&, TransverseID&) = 0;
	virtual void connect(URI&, TransverseID&) = 0;
protected:
	virtual void __abstractClassKludge() override {};
};

class OpenRouteProxy;

class OpenRoute : public PassByReference {
public:
	typedef OpenRouteProxy ProxyClass;
	virtual RouteToken supplyEndpointBus(BusID&) = 0;
	virtual void completeRoute(RouteToken&, ConnectionID&) = 0;
	virtual ConnectionID getConnectionID() = 0;
protected:
	virtual void __abstractClassKludge() override {};
};

class ServiceOfferingProxy;

class ServiceOffering : public PassByReference {
public:
	typedef ServiceOfferingProxy ProxyClass;
	virtual OpenRoute request() = 0;
protected:
	virtual void __abstractClassKludge() override {};
};

class BusMasterProxy;

class BusMaster : public PassByReference {
public:
	typedef BusMasterProxy ProxyClass;
	virtual ConnectionID getNeonateID() = 0;
	virtual void offer(ServiceOffering&, TransverseID&) = 0;
	virtual ProspectiveRoute discover(TransverseID&) = 0;
	virtual void connect(OpenRoute&, ProspectiveRoute&) = 0;
	virtual void requestConnection(OpenTransport&, BusID&) = 0;
	virtual void registerServer(TransportServer&, URI&) = 0;
protected:
	virtual void __abstractClassKludge() override {};
};

