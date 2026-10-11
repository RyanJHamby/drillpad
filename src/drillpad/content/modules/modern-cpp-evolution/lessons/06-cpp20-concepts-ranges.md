# C++20 & Beyond: Concepts, Ranges, Coroutines (Overview)

## Feature 1: Concepts (Type Constraints)

```cpp
// Before C++20: Compiler error is long and confusing
template<typename T>
void sort_collection(T& c) {
  std::sort(c.begin(), c.end());
}
sort_collection(42); // Error: "int has no member begin()"
// Error spans 50 lines of template instantiation noise

// C++20 Concepts: Clear constraint
template<typename T>
requires std::ranges::random_access_range<T>
void sort_collection(T& c) {
  std::sort(c.begin(), c.end());
}
sort_collection(42); // Error: "int does not model random_access_range"
// Clear, actionable error message
```

**Why it matters:**
- Compiler errors are human-readable
- Generic code is more robust
- Interface is explicit

**Production adoption:** Low (most codebases still use C++17)

## Feature 2: Ranges (Expressive Iteration)

```cpp
// C++11 (verbose):
std::vector<int> prices = {100, 50, 200, 75};
std::vector<int> filtered;
std::copy_if(prices.begin(), prices.end(), 
             std::back_inserter(filtered),
             [](int p) { return p > 100; });

// C++20 Ranges (concise):
std::vector<int> prices = {100, 50, 200, 75};
auto filtered = prices 
  | std::views::filter([](int p) { return p > 100; })
  | std::views::transform([](int p) { return p * 1.1; });

// Or with ranges::to:
auto filtered = prices
  | std::views::filter([](int p) { return p > 100; })
  | std::ranges::to<std::vector>();
```

**Why it matters:**
- Functional programming style
- Lazy evaluation (efficient)
- Composable operations

**Production adoption:** Low (standard library adoption still ongoing)

## Feature 3: Coroutines (Async Code)

```cpp
// Traditional async (callbacks):
void fetch_order(int id, Callback<Order> done) {
  async_http_get("/order/" + id, [done](auto response) {
    auto order = parse(response);
    done(order);
  });
}

// C++20 Coroutines (sequential-looking):
Order fetch_order(int id) {
  auto response = co_await async_http_get("/order/" + id);
  co_return parse(response);
}

// Caller still async:
void process() {
  auto order = co_await fetch_order(123);
  process(order);
}
```

**Why it matters:**
- Async code reads like sync code
- No callback hell
- Better error handling

**Production adoption:** Very low (compiler support still incomplete)

## Feature 4: Spaceship Operator (<=>)

```cpp
// Before C++20 (verbose comparison):
struct Order {
  bool operator<(const Order& other) const {
    if (price != other.price) return price < other.price;
    if (symbol != other.symbol) return symbol < other.symbol;
    return id < other.id;
  }
  // Also need >, <=, >=, == (more code)
};

// C++20 (one operator):
struct Order {
  auto operator<=>(const Order&) const = default;
};
// Compiler generates all 6 comparison operators!
```

**Why it matters:**
- Less boilerplate
- Consistent comparison semantics

**Production adoption:** Growing (but not critical)

## When to Use C++20 Features

```
Enterprise/Legacy Codebases:
  - C++11 (must know)
  - C++17 (widely used)
  - C++20 (rare, bleeding edge)

Startups/New Projects:
  - C++17 (default)
  - C++20 (optional, if compiler support good)
  - C++23 (not yet)

Trading Firms:
  - C++11 (baseline everywhere)
  - C++17 (increasingly common)
  - C++20 (used in advanced teams, not mandatory)
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "I've never heard of C++20" (it exists, good to know)
- "Concepts will replace all template code" (they're complementary)
- "Coroutines will replace threading" (different use cases)

✅ **Green flags:**
- "Concepts improve template error messages"
- "Ranges provide functional composition"
- "I know when C++20 is overkill for my codebase"

## Summary: What You Need to Know

```
For interviews (priority order):
  1. C++11: Move, smart pointers, auto, lambdas (MUST know)
  2. C++17: Structured bindings, optional, variant (SHOULD know)
  3. C++20: Concepts overview (NICE to know)

For trading firms specifically:
  1. Move semantics (performance)
  2. Smart pointers (safety)
  3. Constexpr (compile-time optimization)
  4. RAII (no memory leaks)
  
  Bonus: C++17 features (if codebase uses it)
  Bonus+: C++20 concepts (if you're senior)
```

## Quick Reference: Feature Adoption Timeline

```
2011: C++11 released (move, smart pointers, lambdas)
2014: C++14 released (minor improvements)
2017: C++17 released (optional, variant, structured bindings)
2020: C++20 released (concepts, ranges, coroutines)
2023: C++23 released (latest, slow adoption)

Most production C++ code: C++11 or C++17
Cutting edge: C++20
Legacy: C++98 (rare now, but exists)
```

