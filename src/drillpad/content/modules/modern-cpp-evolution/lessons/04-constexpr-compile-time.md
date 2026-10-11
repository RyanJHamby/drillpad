# Constexpr & Compile-Time Evaluation

## When Code Runs: Compile-Time vs Runtime

```cpp
// Runtime (normal function):
int factorial(int n) {
  return n <= 1 ? 1 : n * factorial(n-1);
}
int result = factorial(5); // Runs at runtime (~10 CPU cycles)

// Compile-time (constexpr function):
constexpr int factorial(int n) {
  return n <= 1 ? 1 : n * factorial(n-1);
}
constexpr int result = factorial(5); // Compiler computes this → compiles to "120" (zero runtime cost!)
```

**Impact: Result is baked into binary, zero runtime cost**

## When to Use Constexpr

### Use Case 1: Compile-Time Constants

```cpp
// Pre-C++11: Magic numbers (unclear)
int cache_size = 1024 * 1024; // Why 1M? Unknown

// C++11: constexpr (clear)
constexpr int cache_size = 1024 * 1024; // Compile-time constant
constexpr int max_orders = 10000;

// Use:
std::array<Order, max_orders> orders; // Array size must be compile-time
```

### Use Case 2: Type-Level Computations

```cpp
// Trading: Calculate bit positions at compile-time
constexpr int order_id_bits = 16;
constexpr int symbol_bits = 8;
constexpr int side_bits = 1;

constexpr int order_id_shift = symbol_bits + side_bits;
constexpr int symbol_shift = side_bits;

// Compiler computes these shifts → zero runtime overhead
```

### Use Case 3: Compile-Time Type Checking

```cpp
// Check dimensions at compile-time
template<int Rows, int Cols>
class Matrix {
  static_assert(Rows > 0 && Cols > 0, "Matrix must be positive");
  // Compile error if you try: Matrix<-1, 5> matrix;
};

// Check capacity at compile-time
template<int Size>
class FixedBuffer {
  static_assert(Size >= 1 && Size <= 1000000, "Size out of range");
};
```

## Constexpr in Production Code

```cpp
// Problem: Order matching latency-critical
// Traditional lookup: O(log n) = 100 operations per order

// Solution: Constexpr lookup table
constexpr auto build_symbol_map() {
  std::array<int, 256> map = {};
  map['A'] = 1;
  map['B'] = 2;
  map['C'] = 3;
  // ... build full 256-entry lookup table at compile-time
  return map;
}

constexpr auto symbol_map = build_symbol_map(); // Computed at compile-time

// At runtime: Direct array lookup (1 CPU cycle)
int get_symbol_id(char c) {
  return symbol_map[c]; // O(1), zero-cost abstraction
}
```

## Interview Answer: When to Optimize with Constexpr

**Q: "Order matching is slow. How do you optimize?"**

Weak answer:
```
"Use caching?"
(❌ Doesn't think about compile-time)
```

Strong answer:
```
"Check if computations can move to compile-time (constexpr):
  1. Symbol lookups? Pre-compute mapping (constexpr)
  2. Price rounding? Pre-compute table (constexpr)
  3. Side conversion? Pre-compute table (constexpr)
  
  Result: O(1) lookup instead of O(log n) search
  Speedup: 100x for these operations
  
  Cost: Larger binary (lookup tables), zero runtime"
(✅ Shows optimization thinking)
```

## Constexpr Limitations & Workarounds

```cpp
// Can't call non-constexpr functions in constexpr context:
void expensive_operation() { /* slow */ }

// This doesn't work:
constexpr int result = expensive_operation(); // Compile error!

// Workaround: Make function constexpr if possible
constexpr int fast_operation() { /* must be computable at compile-time */ }
constexpr int result = fast_operation(); // OK

// Or use if constexpr (C++17) for runtime decision:
if constexpr (std::is_same_v<T, int>) {
  // Compile-time branch for int
} else {
  // Compile-time branch for other types
}
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "Constexpr is just for constants" (it's for compile-time computation)
- "Constexpr makes things slower" (no, compile-time = zero runtime)
- "I don't understand constexpr" (needed for modern C++)

✅ **Green flags:**
- "Use constexpr for compile-time lookup tables"
- "Move computation to compile-time if possible"
- "If constexpr for type-specific branches"

