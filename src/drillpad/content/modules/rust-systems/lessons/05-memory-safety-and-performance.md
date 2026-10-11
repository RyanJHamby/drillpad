# Memory Safety & Performance: The Rust Trade-Off

## Overview

Rust prevents memory unsafety at compile time. But this has performance costs. This lesson covers:
1. Where Rust's safety guarantees add overhead
2. When `unsafe` is justified (and when it's not)
3. Zero-cost abstractions: when the compiler optimizes away safety checks
4. Real-world: balancing correctness and speed

---

## The Safety Overhead

Rust's borrow checker prevents use-after-free, double-free, and data races. But:

```rust
// Safe Rust: Borrow checker checks at runtime
fn modify_and_read(v: &mut Vec<i32>) {
    v.push(42);           // Borrow checker tracks: exclusive borrow
    let x = v.first();    // Borrow checker: create shared borrow
    println!("{:?}", x);  // Borrow checker: release shared borrow
    v.push(43);           // Borrow checker: create exclusive borrow again
}

// Cost: Extra bookkeeping in the type system
// Benefit: No segfaults, no use-after-free
```

**Compile-time vs runtime:**
- Borrow checker: Compile-time (0 overhead if code compiles)
- Bounds checking: Runtime (prevents out-of-bounds)
- Reference counting (Rc, Arc): Runtime (atomic ops)

---

## Bounds Checking: When It Matters

```rust
// Runtime check: is index < len?
fn access_unchecked(v: &[i32], i: usize) -> i32 {
    v[i]  // Implicit bounds check (panic if i >= v.len())
}

// Cost: ~5-10 CPU cycles per access (branch + panic path)

// Unsafe: no check
fn access_fast(v: &[i32], i: usize) -> i32 {
    unsafe { *v.get_unchecked(i) }  // Trust me, i < v.len()
}

// Cost: 0 cycles (direct memory access)
```

**When is bounds checking overhead significant?**

```rust
// Inner loop: 1B elements, 1M iterations
let mut sum = 0;
for i in 0..v.len() {
    sum += v[i];  // Bounds check per iteration
}
// Cost: 1M bounds checks = ~5M cycles = 1-5ms overhead

// Unsafe alternative:
let mut sum = 0;
for i in 0..v.len() {
    sum += unsafe { *v.get_unchecked(i) };  // No check
}
// Cost: 0, but if i ever >= v.len(), undefined behavior
```

**Verdict:** Bounds checking overhead is **real for tight loops**, but:
- Branch predictors often optimize it away
- SIMD operations can amortize it
- Usually: correct code > micro-optimized code

---

## Reference Counting: The Shared Ownership Cost

```rust
// Arc: atomic reference counting (thread-safe)
use std::sync::Arc;

let data = Arc::new(vec![1, 2, 3]);
let data2 = Arc::clone(&data);  // atomic increment (1-2 cycles)

// Rc: non-atomic reference counting (single-threaded)
use std::rc::Rc;

let data = Rc::new(vec![1, 2, 3]);
let data2 = Rc::clone(&data);  // non-atomic increment (~0.5 cycles)

// Cost per clone: Arc ~2 cycles, Rc ~0.5 cycles
// Cost of drop: Arc ~2 cycles (atomic decrement)
```

**When Rc/Arc overhead matters:**

```rust
// Hot path: allocate 1M small objects
for i in 0..1_000_000 {
    let data = Arc::new(i);  // Arc allocation + init + refcount
    process(data);
}

// Better: allocate once, share
let data = Arc::new(vec![0..1_000_000]);
for i in 0..1_000_000 {
    let ref_i = Arc::clone(&data);  // Just refcount increment
    process(ref_i);
}
```

---

## Zero-Cost Abstractions: When Safety is Free

Modern compilers (LLVM) optimize away safety checks:

```rust
// Safe Rust (looks like overhead)
fn sum(v: &[i32]) -> i32 {
    let mut s = 0;
    for &x in v {
        s += x;  // Iterator loop (abstraction)
    }
    s
}

// Manual unsafe (what you'd do in C)
fn sum_unsafe(v: &[i32]) -> i32 {
    let mut s = 0;
    let ptr = v.as_ptr();
    for i in 0..v.len() {
        s += unsafe { *ptr.add(i) };  // Manual pointer arithmetic
    }
    s
}

// Compiled assembly: IDENTICAL (compiler inlines & optimizes both)
// Cost: 0 (compiler is smart)
```

**Benchmark result:**
```
Safe loop:   4.2ns per element
Unsafe loop: 4.2ns per element
Overhead:    0% (LLVM optimized both to same code)
```

---

## Unsafe: When It's Justified

Unsafe Rust bypasses compiler checks. Use only when:
1. **Correctness is obvious** (bounds check elimination in tight loop)
2. **Performance is critical** (profiler shows it's the bottleneck)
3. **Alternative is worse** (incorrect algorithm)

**Good use case:**

```rust
// SIMD operations require unsafe pointer manipulation
#[target_feature(enable = "avx2")]
unsafe fn simd_sum(v: &[i32]) -> i32 {
    // ... intrinsics require unsafe
}

// Correctness: clear (vector width is known, no OOB possible)
// Performance: 8x faster than scalar (SIMD)
// Alternative: scalar loop (50% performance loss for SIMD hardware)
```

**Bad use case:**

```rust
// Bounds check elimination when bounds are dynamic
fn access(v: &[i32], i: usize) -> Option<i32> {
    if i < v.len() {
        Some(unsafe { *v.get_unchecked(i) })  // OK, bounds checked above
    } else {
        None
    }
}

// WRONG: This is just v[i] with extra steps. Compiler optimizes bounds check.
fn access_wrong(v: &[i32], i: usize) -> i32 {
    unsafe { *v.get_unchecked(i) }  // BAD: unchecked without validation
}
```

---

## Performance Profiling: Where Safety Actually Costs

```bash
# Profile bounds checking overhead
cargo build --release
perf record -g ./benchmark
perf report  # Look for panic_bounds_check symbol

# If bounds_check is <1% of runtime, don't optimize
# If >5%, consider:
# 1. Unsafe bounds elimination (if safe)
# 2. Algorithm change (avoid indexing)
# 3. SIMD (amortize bounds check)
```

---

## Real-World Example: HashMap Iteration

```rust
// Safe: iterator (bounds-safe, but allocates)
let mut map = HashMap::new();
for (k, v) in &map {
    process(k, v);  // Iterator handles bounds
}

// Unsafe: direct bucket access (faster, but error-prone)
unsafe {
    for bucket in &map.buckets {
        if bucket.is_occupied() {
            process(&bucket.key, &bucket.value);
        }
    }
}

// Actual performance: ~5-10% difference
// Actual safety cost: map.buckets can be resized
// Verdict: Iterator is safer AND usually fast enough
```

---

## Key Takeaways

1. **Most safety overhead is compile-time** (no runtime cost)
2. **Bounds checking is real but usually negligible** (branch prediction hides it)
3. **Arc/Rc overhead matters in allocation-heavy loops** (clone wisely)
4. **LLVM is smart** (safe and unsafe often compile to identical code)
5. **Profile before optimizing** (don't guess where overhead is)
6. **Unsafe = responsibility** (correctness is now YOUR job)

---

## Q&A

**Q: Should I use `unsafe` to avoid bounds checks?**

Only if:
1. Bounds check is on hot path (profiler confirms)
2. Check is redundant (you proved bounds earlier)
3. Unsafe block is small and obviously correct

```rust
// OK: bounds proven above
if i < v.len() {
    return unsafe { v.get_unchecked(i) };
}

// NOT OK: unchecked access with no proof
unsafe { v.get_unchecked(i) }
```

**Q: What's the difference between Rc and Arc?**

Rc: non-atomic (single-threaded, ~0.5 cycles per clone)
Arc: atomic (thread-safe, ~2 cycles per clone)

Use Rc in single-threaded code (10x faster). Use Arc only if you need Send + Sync.

**Q: Does optimization always eliminate bounds checks?**

No. If bounds can't be proven at compile time, check stays. Example:

```rust
for i in 0..len {
    v[i]  // Check can be hoisted (loop invariant)
}

let i = user_input();
v[i]  // Check stays (runtime value)
```

**Q: When is use-after-free prevented by Rust?**

Always. Borrow checker prevents returning references to stack variables:

```rust
fn create_ref() -> &i32 {  // Compiler error
    let x = 5;
    &x  // Can't return reference to stack var
}
```

This is **zero-cost**: error caught at compile time, no runtime overhead.
