# Atomics & Compare-and-Swap: Lock-Free Primitives

## The Core Problem with Locks

```cpp
int counter = 0;
Mutex m;

// Thread 1
m.lock();
counter++;
m.unlock();

// Thread 2
m.lock();
counter++;
m.unlock();
```

Why this works: Mutex ensures only one thread accesses counter at a time.

Why this is slow: Every operation requires a syscall to acquire/release the lock.

Lock overhead (order of magnitude):
- Lock/unlock cycle: ~50-100 nanoseconds
- Actual increment: ~1 nanosecond

**Locks are 50-100x slower than the operation they protect.**

For high-frequency operations (trading systems, lock-free queues), this is unacceptable.

## Atomic Operations: Hardware-Assisted Synchronization

Modern CPUs have instructions that guarantee atomic updates without locks:

```cpp
std::atomic<int> counter = 0;

// Thread 1
counter++;  // Atomic increment, no lock

// Thread 2
counter++;  // Atomic increment, no lock
```

**How the CPU does it:**
- `LOCK INC` instruction (x86)
- Memory fence (prevents reordering)
- Hardware ensures only one CPU can execute this instruction at a time (via cache coherency)

**Cost:** ~5-10 nanoseconds (still slower than non-atomic, but 5-10x faster than lock)

## Compare-and-Swap (CAS): The Foundation

CAS is the most fundamental atomic operation. All lock-free algorithms are built on it.

```cpp
// Pseudocode
atomic<int> value = 0;

// CAS(address, expected, new_value)
// If *address == expected, set *address = new_value and return true
// Otherwise, leave *address unchanged and return false

bool success = value.compare_exchange_strong(0, 1);
// If value was 0, set it to 1 and return true
// If value was not 0, return false
```

### Real Example: Lock-Free Counter

```cpp
std::atomic<int> counter = 0;

void increment() {
    while (true) {
        int old_value = counter.load();
        int new_value = old_value + 1;
        
        // Try to swap: if counter is still old_value, set to new_value
        if (counter.compare_exchange_weak(old_value, new_value)) {
            break;  // Success
        }
        // If CAS failed, loop and try again with new old_value
    }
}
```

**Flow:**
1. Read current counter (0)
2. Calculate new value (1)
3. CAS: "If counter is 0, set to 1"
4. If another thread changed it, CAS returns false
5. Loop and retry with the new value

## When CAS Works Well

| Scenario | Performance | Notes |
|---|---|---|
| **Low contention** (few threads) | Excellent | No conflicts, CAS succeeds first try |
| **High contention** (many threads) | Acceptable | CAS loops, but still faster than lock |
| **Very high contention** (100+ threads) | Degraded | Lock might be faster (fewer retries) |

**Why?** As more threads compete, more CAS failures happen, more retries. Eventually locks win.

## Compare-and-Swap Pitfalls

### Pitfall 1: ABA Problem

```cpp
atomic<ptr> node = A;

// Thread 1: "If node is A, change to B"
node.compare_exchange_strong(A, B);

// Thread 2 (concurrently):
// Removes A from list
// Adds A back
// Now node is A again (but a different A!)
```

**Problem:** CAS succeeds but we're working with the wrong A.

**Solution:** Use versioning (store version + pointer):

```cpp
struct VersionedPtr {
    int version;
    Node* ptr;
};

// CAS now changes both version and pointer
// ABA becomes AVBA (versions are different)
```

### Pitfall 2: Busy-Waiting (Thundering Herd)

```cpp
while (!cas(&lock, 0, 1)) {
    // Spin, burning CPU
}
```

This wastes CPU cycles. Better:

```cpp
while (!cas(&lock, 0, 1)) {
    std::this_thread::yield();  // Let other threads run
}
```

Or use the OS: condition variables, futex, etc.

## Interview Pattern: Lock-Free vs Locks

```
Q: "You need to implement a counter that 100 threads increment concurrently.
   Would you use a lock or atomic CAS?"

Weak answer:
  "Use a lock, it's simpler"
  (❌ Ignores performance requirements)

Strong answer:
  "Depends on contention:
  
  1. First: measure the workload
     - If each thread increments once → low contention → atomics win
     - If each thread increments 1M times → high contention → lock might win
  
  2. For 100 threads, each incrementing N times:
     - Lock: mutual exclusion, ~50ns per increment in lock
     - Atomic: no lock, ~5ns per increment (plus retries if CAS fails)
     
     At high contention, CAS retries add up.
     At low contention, CAS wins big.
  
  3. Measurement approach:
     - Implement both
     - Benchmark with actual workload
     - Profile: time in lock vs time in CAS loops
  
  4. For this specific case (simple counter):
     Atomic is better. Reasons:
     - Counter is high-frequency operation
     - CAS will rarely fail (no complex logic)
     - Lock overhead is significant
     
     Estimated speedup: 2-3x with atomics
  
  5. If it were a complex operation:
     Then lock might be better (less CAS retry loops)"

Why this signals good judgment:
  - You measured before deciding (not "atomics are always better")
  - You understood the tradeoff (atomics fast but retry on conflict)
  - You knew when each wins (low vs high contention)
  - You'd benchmark to validate assumptions
```

## Atomic Memory Ordering (Brief Preview)

Atomics have ordering guarantees:

```cpp
std::atomic<int> x = 0;

x.store(1, std::memory_order_relaxed);   // No synchronization
x.store(1, std::memory_order_release);   // Synchronizes with loads
int v = x.load(std::memory_order_acquire);
```

This is covered in depth in "Memory Ordering" lesson.

## What This Signals

- You understand hardware synchronization (not just locks)
- You know when lock-free is worth the complexity
- You're aware of pitfalls (ABA, busy-waiting)
- You'd measure before choosing a synchronization primitive
