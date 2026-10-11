# Move Semantics & Rvalue References: Performance & RAII

## The Problem: Unnecessary Copying

```cpp
vector<int> create_large_vector() {
  vector<int> result(1000000); // 1M elements
  // ... fill with data ...
  return result; // What happens?
}

// Before C++11 (copy):
vector<int> v = create_large_vector();
// Allocate result vector (1M ints = 4MB)
// Copy 4MB of data from function stack to v
// Destroy temporary result
// Total: 8MB copied, one vector destroyed

// With C++11 move:
vector<int> v = create_large_vector();
// Allocate result vector (1M ints = 4MB)
// MOVE ownership from result to v (just swap pointers)
// Destroy temporary result (now empty, fast)
// Total: 0MB copied, just pointer swap
```

**Impact: 100-1000x faster for large objects**

## Understanding Lvalue vs Rvalue References

```cpp
int x = 5;          // x is lvalue (has address, persists)
int&& y = 5;        // 5 is rvalue (temporary, will be destroyed)

vector<int> v;
v = create_vector(); // create_vector() returns rvalue
                     // We should MOVE, not copy

// Rvalue reference = "I can steal your resources, you're dying anyway"
```

## The Move Constructor & Assignment

```cpp
class Vector {
  int* data;
  int size;
  
public:
  // Copy constructor (lvalue)
  Vector(const Vector& other) {
    data = new int[other.size];
    memcpy(data, other.data, other.size * sizeof(int));
    size = other.size;
    // Cost: allocate + copy all data
  }
  
  // Move constructor (rvalue)
  Vector(Vector&& other) noexcept {
    data = other.data;      // Steal the pointer
    size = other.size;
    other.data = nullptr;   // Leave other empty
    other.size = 0;
    // Cost: just pointer swap (nanoseconds)
  }
};
```

**Interview answer:**

```
Q: "Vector copy is slow. How do you optimize?"

"Use move constructor:
  1. Detect if source is temporary (rvalue reference)
  2. Steal internal pointers instead of copying data
  3. Leave source empty (it will be destroyed)
  
  Cost drops from O(n) to O(1)
  Speedup: 100x-1000x for large vectors"
```

## Move Semantics in Collections

```cpp
// Without move (slow):
vector<string> words;
words.push_back("hello"); // Copy "hello" into vector
words.push_back("world"); // Copy "world" into vector

// With move (fast):
vector<string> words;
words.push_back(string("hello")); // Move temporary into vector
words.push_back("world"_s);       // Move string_view into vector

// Or even better (C++17):
vector<string> words = {"hello", "world"}; // One allocation, no copies
```

## Perfect Forwarding: Advanced Move Pattern

```cpp
// Problem: Want to pass arguments without copying
void process(const string& s) { ... }

// Naive approach:
template<typename T>
void wrapper(T t) {
  process(t); // If T = string&&, we lose rvalue info!
}

// Solution: Perfect forwarding
template<typename T>
void wrapper(T&& t) {  // T&& is universal reference
  process(std::forward<T>(t)); // Preserves lvalue/rvalue
}

wrapper(string("hello")); // Rvalue stays rvalue
string s = "world";
wrapper(s);               // Lvalue stays lvalue
```

**Why it matters:**
- Template code can preserve rvalue semantics
- No unnecessary copies through multiple layers
- Trading interview signal: Advanced C++ knowledge

## Common Mistakes with Move

### Mistake 1: Moved-from object is not empty

```cpp
// Wrong:
Vector v1 = create_vector();
Vector v2 = std::move(v1);
cout << v1.size(); // Undefined! Don't use v1 anymore

// Better pattern:
Vector v1 = create_vector();
Vector v2 = std::move(v1);
v1 = Vector(); // Explicitly reset if you need to use it
```

### Mistake 2: Forgetting noexcept

```cpp
// Without noexcept:
Vector(Vector&& other) {
  data = other.data;
  other.data = nullptr;
}

// Problem: If this throws, data might leak
// vector::push_back won't use move constructor if it might throw!

// Correct:
Vector(Vector&& other) noexcept {
  data = other.data;
  other.data = nullptr;
}

// Now vector uses move instead of copy
```

## Real Trading Example: Order Book

```cpp
// Naive (slow):
OrderBook book;
vector<Order> orders = query_database(); // Copy all orders
for(const auto& order : orders) {
  book.insert(order); // Copy again per order
}

// With move (fast):
OrderBook book;
vector<Order> orders = query_database(); // Move
for(auto& order : orders) {
  book.insert(std::move(order)); // Move each order
}

// Result: 10,000 orders
  Naive: 10,000 copies = 5MB copied
  Move: 0 copies = pointer swaps only
  Speedup: 1000x
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "Move is just for performance" (wrong; it's also about semantics)
- "I always use shared_ptr" (loses move semantics, costs extra)
- "Move constructors are complicated" (should be simple: steal pointers)
- "I don't use move in template code" (missing perfect forwarding)

✅ **Green flags:**
- "Move constructor should be noexcept"
- "Std::move is only a cast, compiler does the work"
- "Use perfect forwarding with universal references"
- "Moved-from objects are in a valid but unspecified state"

## Quick Checklist

**When designing a class:**

- [ ] Need a copy constructor? Also need move constructor
- [ ] Move should be noexcept (allows optimizations)
- [ ] Can steal internal pointers? Implement move
- [ ] In templates? Use perfect forwarding (std::forward)
- [ ] Using smart pointers? Move is automatic

