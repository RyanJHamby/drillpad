# Smart Pointers & Ownership Semantics: Memory Safety

## The Problem: Raw Pointer Chaos

```cpp
// C++98 (raw pointers):
void process_order(Order* order) {
  if (!validate(order)) {
    delete order;    // Cleanup path 1
    return;
  }
  
  process(order);
  delete order;      // Cleanup path 2
  
  // But what if process() throws? Memory leak!
  // What if someone calls process_order(nullptr)? Crash!
}

Result: Every function with a pointer needs manual cleanup
Cost: Memory leaks everywhere, hard to reason about ownership
```

**Modern C++ (smart pointers):**

```cpp
void process_order(std::unique_ptr<Order> order) {
  if (!validate(order.get())) {
    return;  // order auto-deletes on scope exit (RAII)
  }
  
  process(order);
  // order auto-deletes, no manual cleanup needed
}

Result: Ownership is explicit, cleanup is automatic
Cost: Zero runtime overhead (compiler optimizes it away)
```

## Smart Pointer Types

### unique_ptr: Exclusive Ownership

```cpp
std::unique_ptr<Order> order1 = std::make_unique<Order>();

// Only one owner at a time
std::unique_ptr<Order> order2 = std::move(order1); // order1 becomes nullptr
// order1.use() would crash (good, prevents double-use bugs)

// When order2 goes out of scope: automatically delete

// Cost: Zero overhead (compiler optimizes to raw pointer)
```

**When to use:** Almost always (default choice)

### shared_ptr: Reference Counting

```cpp
std::shared_ptr<Order> order1 = std::make_shared<Order>();
std::shared_ptr<Order> order2 = order1; // Reference count = 2

// Both order1 and order2 point to same object
// When order1 goes out of scope: count = 1 (not deleted)
// When order2 goes out of scope: count = 0 (delete)

// Cost: Atomic increment/decrement on each copy (small but non-zero)
```

**When to use:** Only when you need multiple owners
Example: Cache where entry can be held by multiple consumers

### weak_ptr: Non-Owning Reference

```cpp
std::weak_ptr<Order> observer = order1; // Doesn't increment count

// Can convert to shared_ptr if object still alive:
if (auto order = observer.lock()) {
  process(order); // Safe to use
} else {
  // Object was already deleted
}

// Cost: Tiny overhead (for lock operation)
```

**When to use:** Breaking reference cycles (shared_ptr pointing to each other)

## RAII Pattern: Resource Acquisition Is Initialization

```cpp
// Before RAII (manual cleanup):
void read_file(string filename) {
  FILE* f = fopen(filename.c_str(), "r");
  if (!f) return; // Leak: file never closed
  
  if (read_fails(f)) {
    // Leak: file never closed
  }
  
  fclose(f); // Manual cleanup (easy to forget)
}

// With RAII (automatic cleanup):
void read_file(string filename) {
  std::ifstream f(filename); // Opens on construction
  if (!f) return;            // Closed on exit (RAII)
  
  if (read_fails(f)) {
    // Closed on exit (RAII) - automatic
  }
  // f destroyed, file closed automatically
}

Pattern:
  Constructor: Acquire resource
  Destructor: Release resource
  No explicit cleanup needed
```

## RAII + Ownership = Memory Safety

```cpp
// Quiz: Can you spot the leak?
void process_orders(vector<Order*> orders) {
  for (auto order : orders) {
    try {
      process(order);
    } catch (...) {
      // Leak: nobody deletes order
    }
  }
}

// Answer: If process() throws, loop exits, order never freed

// Fix: Use smart pointers (automatic cleanup):
void process_orders(vector<unique_ptr<Order>> orders) {
  for (auto& order : orders) {
    try {
      process(order);  // If throws, order destructs anyway
    } catch (...) {
      // No leak: order still destroyed in catch handler
    }
  }
}

// Even better: modern error handling
void process_orders(vector<unique_ptr<Order>> orders) {
  for (auto& order : orders) {
    process(order);  // If throws, loop exits, vectors destruct (RAII)
  }
}
```

## Trading Interview: Order Book

**Q: "You have 1M orders in memory. How do you prevent memory leaks?"**

Weak answer:
```
"I'm careful to delete each order"
(❌ Manual cleanup is error-prone)
```

Strong answer:
```
"Use RAII: unique_ptr<Order> for each order.
 
 When order is filled:
   unique_ptr destructs → delete automatically
   
 When order book shuts down:
   vector<unique_ptr> destructs → all orders deleted
   
 If processing throws:
   Exception unwinds → destructs happen anyway
   
 Result: Zero memory leaks, no manual cleanup code"
(✅ Shows RAII mastery)
```

## Common Patterns

### Pattern 1: Factory with unique_ptr

```cpp
// Return ownership to caller
std::unique_ptr<Order> create_order(const OrderRequest& req) {
  return std::make_unique<Order>(req); // Move semantics automatic
}

// Caller owns it:
auto order = create_order(req);
// ... use it ...
// Auto-deleted when order goes out of scope
```

### Pattern 2: Object holding sub-components

```cpp
class OrderBook {
  std::vector<std::unique_ptr<Order>> orders;
  std::unique_ptr<Cache> order_cache;
  
  // Ownership is clear: OrderBook owns all sub-objects
  // When OrderBook destructs: all sub-objects auto-delete
};
```

### Pattern 3: Passing ownership

```cpp
// Caller transfers ownership to callee
void add_order(std::unique_ptr<Order> order) {
  book.add(std::move(order));
  // Original 'order' is now nullptr
  // Compiler prevents accidental use after move
}

auto order = std::make_unique<Order>();
add_order(std::move(order)); // Explicit: we're moving
// order is now nullptr, attempting order->... would crash (catches bugs)
```

## Performance: Zero-Cost Abstraction

```cpp
// Smart pointer overhead:
raw_ptr = new Order(); // Cost: malloc
unique_ptr = make_unique<Order>(); // Cost: malloc (same!)

delete raw_ptr; // Manual cleanup
// unique_ptr ~Order() → // Automatic cleanup (same!)

Benchmark:
  Raw pointers: 1.0x (baseline)
  unique_ptr: 1.0x (compiler optimizes away completely)
  shared_ptr: 1.05x (atomic increment/decrement)

Result: Use unique_ptr everywhere (same speed as raw pointers)
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "I use raw pointers for performance" (unique_ptr is just as fast)
- "Smart pointers are hard to understand" (they're simple: RAII)
- "shared_ptr is the default" (no! use unique_ptr by default)
- "I don't delete anything, garbage collector handles it" (this is C++, not Java)

✅ **Green flags:**
- "unique_ptr by default, shared_ptr only if needed"
- "RAII: resource cleanup on scope exit"
- "Ownership is explicit in the type"
- "Make_unique for exception safety"

## Quick Checklist

**Class design with pointers:**

- [ ] Need a pointer? Use unique_ptr or shared_ptr (not raw)
- [ ] Default to unique_ptr (zero overhead)
- [ ] Multiple owners? Use shared_ptr (rare)
- [ ] Prevent cycles? Use weak_ptr
- [ ] Exception-safe? Yes (RAII handles it)

