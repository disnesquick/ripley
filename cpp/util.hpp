template <typename InnerType>
class SmartPtr {
public:
	SmartPtr(InnerType& contents) : contents(&contents) {};
	SmartPtr(InnerType* contents) : contents(contents) {};
	SmartPtr(SmartPtr&& other) {
		this->contents = other.contents;
		other.contents = nullptr;
	}
	
	InnerType& operator*() {return *contents;}
	
	virtual ~SmartPtr(){};
	
protected:
	InnerType* contents;
};

template <typename InnerType>
class VisitorPtr : public SmartPtr<InnerType>{
public:
	using SmartPtr<InnerType>::SmartPtr;
	
	virtual ~VisitorPtr() {};
};

template <typename InnerType>
class OwnerPtr : public SmartPtr<InnerType>{
public:
	using SmartPtr<InnerType>::SmartPtr;
	
	virtual ~OwnerPtr() {delete this->contents;}
};




