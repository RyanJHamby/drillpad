# C++17: Structured Bindings, Optional, Variant, If Constexpr

## Feature 1: Structured Bindings (Most Practical)

```cpp
// Before C++17:
std::pair<int, std::string> result = lookup_order(id);
int order_id = result.first;
std::string status = result.second;

// C++17:
auto [order_id, status] = lookup_order(id); // Clean, readable

// Works with:
std::tuple<int, string, double> tup = {1, "test", 3.14};
auto [a, b, c] = tup;

std::map<string, Order> orders;
for (auto [symbol, order] : orders) { // Iterate with names
  process(symbol, order);
}
```

**Why it matters:** Reduces boilerplate, improves readability

## Feature 2: std::optional (Null Safety)

```cpp
// Before (raw pointers):
Order* find_order(int id) {
  if (order_exists(id)) {
    return new Order(id); // Caller must remember to delete!
  }
  return nullptr; // Unclear semantics
}

// C++17 (std::optional):
std::optional<Order> find_order(int id) {
  if (order_exists(id)) {
    return Order(id); // Safe, caller knows it might be empty
  }
  return std::nullopt; // Clear semantics
}

// Usage:
if (auto order = find_order(123)) {
  process(*order); // Safe: order definitely exists
} else {
  // Handle missing order
}
```

**Why it matters:** Type-safe nullability, no raw pointer leaks

## Feature 3: std::variant (Type-Safe Union)

```cpp
// Before (unsafe union):
union Response {
  int error_code;
  Order* order;
  // Unclear which is valid!
};

// C++17 (type-safe):
std::variant<Order, std::string> get_order(int id) {
  if (order_exists(id)) {
    return Order(id); // Variant is the order
  } else {
    return "Order not found"; // Variant is the error
  }
}

// Usage:
auto response = get_order(123);
if (std::holds_alternative<Order>(response)) {
  auto order = std::get<Order>(response); // Safe access
} else {
  auto error = std::get<string>(response);
  log_error(error);
}
```

**Why it matters:** Type-safe, compiler-enforced correctness

## Feature 4: If Constexpr (Compile-Time Branching)

```cpp
// Before C++17 (dynamic dispatch):
template<typename T>
void serialize(T value) {
  if (std::is_integral_v<T>) {
    write_int(value); // Runtime check
  } else if (std::is_floating_point_v<T>) {
    write_float(value); // Runtime check
  }
}

// C++17 (compile-time decision):
template<typename T>
void serialize(T value) {
  if constexpr (std::is_integral_v<T>) {
    write_int(value); // This branch compiled for int
  } else if constexpr (std::is_floating_point_v<T>) {
    write_float(value); // This branch compiled for float
  }
}

// Result: Only correct branch compiled, zero runtime if/else
```

**Why it matters:** Zero runtime overhead, type-specific behavior

## Trading Interview: How C++17 Helps

**Q: "Your order processing is slow. You need to handle both int and float prices. How?"**

Weak answer:
```
"Use dynamic dispatch? If statement at runtime?"
(❌ Runtime overhead)
```

Strong answer:
```
"Use if constexpr for compile-time type specialization:

template<typename Price>
void process_order(const Price& price) {
  if constexpr (std::is_integral_v<Price>) {
    // Optimized path for int prices (no float overhead)
    return process_int_price(price);
  } else {
    // Optimized path for float prices
    return process_float_price(price);
  }
}

Result:
  - int prices: compiled without float operations
  - float prices: compiled without int operations
  - Zero runtime if/else overhead
"
(✅ Shows type-specific optimization)
```

## Quick Reference: C++17 Feature Priority

```
Must know:
  ✅ Structured bindings (very common)
  ✅ std::optional (replaces pointer returns)
  ✅ std::variant (safe union)
  
Should know:
  ⚠️ if constexpr (optimization)
  ⚠️ Fold expressions (template metaprogramming)
  
Nice to know:
  ❌ Deduction guides (uncommon)
  ❌ Inline variables (rare use case)
```

