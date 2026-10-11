# Memory Barriers: Acquire/Release, Sequential Consistency

## The Problem: Compiler & CPU Reordering

```
Your code:
  x = 1
  y = 2
  
Compiler/CPU might reorder:
  y = 2        (write to y first, faster)
  x = 1
  
In single-threaded code: who cares? (same result)
In multi-threaded code: DISASTER!

Thread A:         Thread B:
  x = 1             while (x == 0) { }
  flag = true       read y  (expects 2)
  
Execution:
  CPU reorders A: flag = true, then x = 1
  B reads flag = true
  B reads x = 1 (good)
  B reads y = 2 (good)
  
But:
  CPU reorders A: flag = true, then x = 1, then... y?
  B reads flag = true
  B reads y = ?? (not yet written!)
  WRONG!
```

---

## Memory Ordering Guarantees

```
No barrier (relaxed):
  Read/write can reorder
  Fastest, but hardest to reason about
  Use when: you control all accesses to this variable

Acquire (on load):
  All loads after must not move before this
  Prevents subsequent reads from moving up
  
Release (on store):
  All stores before must not move after this
  Prevents prior writes from moving down

Sequential consistency:
  All operations ordered as written
  Slowest, but safest
  Like having barriers everywhere
```

---

## Real Pattern: Publishing Flag

```c
// WRONG (no barriers)
volatile int x = 0;
volatile bool ready = false;

Thread A:
  x = 42;              // write 1
  ready = true;        // write 2
  
Thread B:
  while (!ready) { }   // wait for ready
  printf("%d", x);     // expect x = 42
  
Problem: CPU might write ready=true before x=42!
B might see ready=true, but x still 0.

// CORRECT (with release/acquire)
Thread A:
  x = 42;
  store_release(&ready, true);  // barrier: force x=42 before ready=true
  
Thread B:
  while (!load_acquire(&ready)) { }  // barrier: don't read x until ready
  printf("%d", x);  // guaranteed x = 42
```

---

## Memory Ordering in Code

```cpp
// C++ atomics with explicit ordering
std::atomic<int> x(0);
std::atomic<bool> ready(false);

// Thread A
x.store(42, std::memory_order_release);
ready.store(true, std::memory_order_release);

// Thread B
while (!ready.load(std::memory_order_acquire)) { }
printf("%d", x.load(std::memory_order_acquire));  // guaranteed 42
```

---

## When to Use Which Barrier

```
Relaxed (memory_order_relaxed):
  Use: counter that doesn't coordinate with other operations
  Example: increment a stats counter (no other thread depends on its exact value)
  
Acquire/Release (memory_order_acquire/release):
  Use: synchronization (lock-free queue, flag)
  Example: push to queue (release) → pop reads (acquire)
  
Sequential consistency (memory_order_seq_cst):
  Use: when unsure, or when correctness matters most
  Cost: slower (full barrier both sides)
```

---

## Q&A

**Recall 1:** What does acquire barrier do?

*Must-say:*
- All loads AFTER acquire must not move before it
- Prevents subsequent reads from reordering up
- Ensures prior stores are visible before subsequent loads

**Probe 1:** You use relaxed ordering everywhere. What could go wrong?

*Expected:*
- Data races: two threads see inconsistent state
- Stale reads: thread reads old value
- Lost updates: write gets reordered, overwritten

