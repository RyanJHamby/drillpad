# C++ Gotchas & Edge Cases: Rule of 5, Allocators, Templates, Smart Pointers

## Overview

Interviewers love testing deep C++ knowledge through gotchas and edge cases. This lesson covers:
1. **Rule of 5:** When you need custom copy/move semantics.
2. **Custom allocators:** Why and how (trading systems need predictable allocation).
3. **Iterators vs custom classes:** std::list design, when pointers break.
4. **Templates and concepts:** Modern C++ (C++20) advances.
5. **Smart pointers and memory model:** Ownership, aliasing, reference counting.

---

## Rule of 5: Copy/Move/Destruct

**The rule:** If you define a custom destructor, copy constructor, or copy assignment, define all five:
1. Destructor
2. Copy constructor
3. Copy assignment operator
4. Move constructor (C++11)
5. Move assignment operator (C++11)

**Why it matters:**

```cpp
class Order {
    int* data;  // Dynamically allocated
    
public:
    Order() : data(new int[128]) {}  // Allocate on construction
    
    ~Order() { delete[] data; }  // CUSTOM DESTRUCTOR
    
    // If you define dtor, compiler DOES NOT auto-generate copy/move.
    // BAD: compiler generates default copy (shallow copy of pointer)
    
    // GOOD: explicitly define all five
    
    // Copy constructor (deep copy)
    Order(const Order& other) : data(new int[128]) {
        std::memcpy(data, other.data, 128 * sizeof(int));
    }
    
    // Copy assignment
    Order& operator=(const Order& other) {
        if (this != &other) {
            std::memcpy(data, other.data, 128 * sizeof(int));
        }
        return *this;
    }
    
    // Move constructor (steal resources)
    Order(Order&& other) noexcept : data(other.data) {
        other.data = nullptr;
    }
    
    // Move assignment
    Order& operator=(Order&& other) noexcept {
        if (this != &other) {
            delete[] data;
            data = other.data;
            other.data = nullptr;
        }
        return *this;
    }
};

// Interview trap: What happens if you copy an Order?
Order o1;
Order o2 = o1;  // Calls copy constructor
delete o1;  // Deletes o1.data
o2.data;  // DANGLING POINTER! (if you only have shallow copy)
```

**Modern C++ (C++17+): "Rule of zero"**

```cpp
// BETTER: use std::unique_ptr (RAII)
class Order {
    std::unique_ptr<int[]> data;
    
public:
    Order() : data(std::make_unique<int[]>(128)) {}
    
    // Destructor: implicit (unique_ptr dtor runs)
    // Copy: auto-deleted (unique_ptr is non-copyable)
    // Move: auto-generated (unique_ptr is movable)
    
    // No need to write any of the five!
};

// This is the "rule of zero": use smart pointers, let compiler auto-generate.
```

**Interview question:** "You have a class with a custom destructor. What must you do?"

**Answer:** Define all five (copy ctor, copy assignment, move ctor, move assignment). Or use smart pointers (rule of zero).

---

## Custom Allocators

**Problem:** Standard allocator (malloc) has variable latency. Trading systems need predictable allocation.

```cpp
// Standard vector (bad for latency-critical code)
std::vector<Order> orders;
for (int i = 0; i < 1000000; ++i) {
    orders.push_back(Order{...});  // May trigger malloc, variable latency
}

// Custom allocator (good)
class PoolAllocator {
    static constexpr size_t POOL_SIZE = 1000000;
    std::array<Order, POOL_SIZE> pool;
    std::stack<Order*> free_list;
    
public:
    PoolAllocator() {
        for (size_t i = 0; i < POOL_SIZE; ++i) {
            free_list.push(&pool[i]);
        }
    }
    
    Order* allocate() {
        if (free_list.empty()) throw std::bad_alloc();
        Order* o = free_list.top();
        free_list.pop();
        return o;
    }
    
    void deallocate(Order* o) {
        free_list.push(o);
    }
};

// Using custom allocator with std::vector
std::pmr::vector<Order> orders(alloc);  // Polymorphic allocator (C++17)
// Or: std::vector<Order, CustomAllocator> orders;
```

**Interview gotcha:** "Can you use a custom allocator with STL containers?"

**Answer:** Yes, all STL containers are template-parameterized on `Allocator`. But most use default `std::allocator`. C++17 adds `std::pmr::vector` for polymorphic allocators (runtime-selectable).

**Deep question:** "Why not just pre-allocate the vector?"

**Answer:** Pre-allocation (`reserve()`) is good for simple cases, but:
- Fixed capacity: if you grow beyond reserved, reallocation still happens.
- Memory layout: allocator controls where memory comes from (stack, arena, NUMA node, etc.).
- Predictability: custom allocators guarantee O(1) alloc/free from a bounded pool.

---

## Iterators vs Custom Classes: std::list Design

**Problem:** When should you use iterators vs raw pointers?

```cpp
// std::list is a doubly-linked list
std::list<Order> orders;

// Iterators are stable (remain valid after insert/erase)
auto it = orders.insert(orders.end(), Order{...});

// But std::vector iterators invalidate on reallocation
std::vector<Order> v;
auto it_v = v.begin();
v.push_back(Order{...});  // Reallocation might happen
// it_v is now INVALID
```

**Design decision: When to use what?**

```
Data Structure | Iterators | Stability | Use Case
──────────────────────────────────────────────────
std::vector    | Random    | Insert/erase invalidate | Frequent random access, rare modification
std::list      | Bidirectional | Insert/erase preserve | Frequent insert/erase at known positions
std::deque     | Random    | Insert at ends preserve | Front/back operations, random access
Custom class   | Custom    | User-defined | Special performance requirements
```

**Real example: Order book (trading)**

```cpp
// Bad: std::list (pointer indirection, cache misses)
std::list<Order> buy_orders;
for (const auto& o : buy_orders) {
    process(o);  // Cache miss per node (100+ ns)
}

// Good: std::vector (cache-friendly, contiguous)
std::vector<Order> buy_orders;
for (const auto& o : buy_orders) {
    process(o);  // 4–10 ns per order (in cache)
}

// But if you frequently erase from middle:
// Bad: std::vector (O(n) shifts)
// Good: std::list (O(1) erase)

// Custom solution: Use indexing into vector, swap-erase pattern
std::vector<Order> orders;
// To erase: swap with end, pop_back (O(1) amortized)
auto it = std::find(orders.begin(), orders.end(), order_to_erase);
std::swap(*it, orders.back());
orders.pop_back();  // Fast
```

**Interview question:** "You have a vector of orders. You want to efficiently remove orders that have been filled. How do you do it?"

**Answer:** Use erase-remove idiom:
```cpp
orders.erase(
    std::remove_if(orders.begin(), orders.end(),
                   [](const Order& o) { return o.is_filled(); }),
    orders.end()
);  // O(n), single pass, reuses vector buffer
```

Or swap-erase for single removal:
```cpp
auto it = find_filled_order();
std::swap(*it, orders.back());
orders.pop_back();  // O(1)
```

---

## Templates and Modern C++ Concepts

**Problem:** Templates are powerful but error messages are cryptic.

```cpp
// Generic max function (C++98)
template<typename T>
T max(T a, T b) { return a > b ? a : b; }

// Works for int, double, Order (if operator> is defined)
// But if T doesn't have operator>, error is a 50-line template error

// C++20 Concepts: constrain template parameters
#include <concepts>

template<typename T>
concept Comparable = requires(T a, T b) {
    { a > b } -> std::convertible_to<bool>;
};

template<Comparable T>
T max(T a, T b) { return a > b ? a : b; }

// Now if you pass non-Comparable type, error is clear:
// "error: max<NonComparable> does not satisfy concept Comparable"
```

**Interview gotcha:** "What's the difference between template specialization and overloading?"

```cpp
// Specialization (one template, multiple implementations)
template<typename T> class Container { /* generic */ };
template<> class Container<bool> { /* special case */ };  // Full specialization

// Partial specialization
template<typename T> class Container<std::vector<T>> { /* for vectors */ };

// Overloading (different function signatures)
void process(int x);
void process(double x);
void process(const std::string& x);

// Templates can be specialized; functions overloaded.
```

**Real example: Trading system**

```cpp
// Generic order handler
template<typename OrderType>
void process_order(const OrderType& o) {
    if constexpr (std::is_same_v<OrderType, LimitOrder>) {
        // Limit order logic
        match_against_book(o);
    } else if constexpr (std::is_same_v<OrderType, MarketOrder>) {
        // Market order logic (faster, no matching needed)
        fill_immediately(o);
    }
}

// C++20 concept: make constraints explicit
template<typename T>
concept Order = requires(T o) {
    { o.symbol() } -> std::convertible_to<std::string>;
    { o.quantity() } -> std::convertible_to<int>;
    { o.price() } -> std::convertible_to<double>;
};

template<Order OrderType>
void process_order(const OrderType& o) {
    // Compiler checks OrderType has symbol(), quantity(), price()
    match_against_book(o);
}
```

---

## Shared Memory Model and Memory Ordering

**Problem:** Multi-threaded C++ is hard. What guarantees does the standard give?

```cpp
std::atomic<int> x{0}, y{0};

// Thread 1
x.store(1, std::memory_order_release);  // Release
y.store(1, std::memory_order_release);

// Thread 2
int y_val = y.load(std::memory_order_acquire);  // Acquire
int x_val = x.load(std::memory_order_relaxed);  // Relaxed

// If y_val == 1, is x_val guaranteed to be 1?
// Answer: ONLY if you use release/acquire (not relaxed for x).
```

**Memory ordering levels:**

```
std::memory_order_relaxed:
  Atomicity only. No synchronization.
  x.store(1, relaxed); y.load(relaxed);  // No ordering guarantee

std::memory_order_release (store) / acquire (load):
  One-way synchronization. Release "sends" to acquire.
  x.store(1, release); x.load(acquire);  // y can see x=1

std::memory_order_acq_rel (for compare_exchange):
  Acquire on load, release on store.

std::memory_order_seq_cst:
  Sequential consistency. Total order on all operations.
  Slowest, but strongest guarantee.
```

**Interview question:** "Why would you use memory_order_relaxed?"

**Answer:** For counters where ordering doesn't matter (e.g., hit counter). Fastest.

**Real example: Lock-free order book**

```cpp
std::atomic<Order*> best_bid{nullptr};
std::atomic<Order*> best_ask{nullptr};

// Matcher thread
void update_best_bid(Order* new_bid) {
    best_bid.store(new_bid, std::memory_order_release);
    // Release ensures other threads see the update
}

// Client thread
Order* bid = best_bid.load(std::memory_order_acquire);
// Acquire ensures we see the latest bid
if (bid) process(bid);
```

---

## Smart Pointers: unique_ptr, shared_ptr, weak_ptr

**Problem:** Raw pointers have no ownership semantics. Who deletes?

```cpp
// Bad: ownership unclear
void process_order(Order* o) {
    // Should I delete o? Maybe the caller does. Maybe not. Undefined.
}

// Good: ownership explicit
void process_order(std::unique_ptr<Order> o) {
    // Function owns o, will delete it
}

void process_order_shared(std::shared_ptr<Order> o) {
    // Multiple owners, shared_ptr deletes when last owner is done
}
```

**Gotcha: Circular references with shared_ptr**

```cpp
struct Node {
    std::shared_ptr<Node> next;
};

auto n1 = std::make_shared<Node>();
auto n2 = std::make_shared<Node>();
n1->next = n2;  // n1 owns n2
n2->next = n1;  // n2 owns n1 (CYCLE!)

// Memory leak: n1 and n2 reference each other, both ref_count=1, neither deleted
// FIX: use weak_ptr
struct Node {
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev;  // Non-owning reference
};

n2->prev = n1;  // n2 doesn't own n1 (weak), so no cycle
```

**Interview gotcha:** "What's the cost of shared_ptr?"

**Answer:**
- Size: 16 bytes (2 pointers: data + control block).
- Cost: atomic increment/decrement on copy/destroy (~10-20 ns per operation).
- Indirection: Control block is separate, cache miss on delete.

**When to use:**
- `unique_ptr`: Single owner (fast, zero-cost).
- `shared_ptr`: Multiple owners, cannot avoid cycles.
- `weak_ptr`: Non-owning reference to shared_ptr (breaks cycles).

**Real example: vLLM request handling**

```cpp
// HTTP request handler
std::shared_ptr<Request> req = std::make_shared<Request>(...);

// Queue request for inference
queue.push(req);  // Queue holds a shared_ptr (req not deleted yet)

// Meanwhile, HTTP connection closes
// req (original shared_ptr) goes out of scope
// Queue still holds it (ref_count > 0, not deleted)

// Inference worker dequeues and processes
auto req = queue.pop();
process(req);  // Safe: request still alive, even though HTTP closed

// When worker finishes, ref_count drops to 0, req deleted
```

---

## Story Card: Order Book Allocator Optimization

**Setup:** Trading-firm interview, design an order book for latency < 1 us P99.9.

**Initial approach:** std::map + std::vector (standard allocators).

**Problem:** After ~100K orders, malloc latency spikes (page refill). P99.9 jumps from 1 us to 50 us.

**Solution:** Custom pool allocator for Order structs.

```cpp
// Pre-allocate 1M orders at startup (100 MB)
// Allocation: pop from free-list (10 ns)
// Deallocation: push to free-list (10 ns)

Order* o = allocator.allocate();  // O(1), ~10 ns
// Use order
allocator.deallocate(o);  // O(1), ~10 ns

// Result: P99.9 stable at 1–3 us (eliminated malloc spikes)
```

**Interview follow-up:** "What if we run out of pre-allocated orders?"

**Answer:** Throw std::bad_alloc (fail fast). Or use a hybrid: pool for normal load, malloc for overflow (with latency warning).

---

## Q&A

**Recall 1:** What is the Rule of 5?

*Must-say:*
- If you define a custom destructor, copy constructor, or copy assignment, define all five: destructor, copy ctor, copy assignment, move ctor, move assignment.
- Or use smart pointers (Rule of Zero).

**Probe 1:** You have a `std::vector<Order>`. You want to remove filled orders efficiently. Walk me through the options.

*Expected:*
- Option 1: erase-remove idiom (one pass, stable).
- Option 2: swap-erase for single removal (O(1)).
- Option 3: mark orders as deleted, skip in iteration (lazy deletion).

**Probe 2:** std::list vs std::vector for an order book. Which would you use?

*Expected:*
- Use std::vector (cache-friendly, random access).
- For insert/erase, use erase-remove or swap-erase (faster than list indirection).
- Only use std::list if you frequently iterate and erase simultaneously (which is rare).

**Numeric 1:** A shared_ptr is 16 bytes. You have 1000 requests, each with 2 shared_ptrs. Memory overhead?

*Working:*
- 1000 * 2 * 16 = 32 KB (negligible).
- Control block overhead: ~56 bytes per shared_ptr (depending on implementation).
- Total: 1000 * 2 * 56 = 112 KB (still small).
- Cost: atomic increment on copy (~10 ns), decrement on destroy (~10 ns).

**Numeric 2:** You have a custom allocator that pre-allocates 1M objects (200 bytes each). How much memory?

*Working:*
- 1M * 200 bytes = 200 MB.
- One-time allocation at startup.
- Allocation/deallocation: O(1), ~10 ns (vs malloc 100+ ns).

---

## Questions for the Interviewer

- Do you use custom allocators for performance-critical code?
- How do you handle the Rule of Five in your codebase (smart pointers or manual)?
- Have you hit issues with circular references (shared_ptr cycles)?
- What C++17/C++20 features do you rely on?
