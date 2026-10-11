# Concurrency and Heisenbugs: The Debugging Hardship

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Non-Deterministic Failures

A race condition might manifest once a month, at 3am, under specific timing. You can't reproduce it.

**The trap:** Adding print statements "fixes" it (the print shifts timing, hiding the race).

**This lesson:** Debugging techniques specific to concurrency bugs. (See concurrency-fundamentals and lock-free-systems for conceptual understanding.)

## Why Concurrency Bugs Are Special

```
Sequential code:
  Same input → same output (deterministic)
  Debug: Reproduce locally, use debugger
  
Concurrent code:
  Same input → different output (timing-dependent)
  Debug: Might happen 1% of time, unpredictably
  Adding logging → "fixes" it (Heisenbug)
```

## Symptom: The Heisenbug

**Heisenbug:** A bug that disappears when you try to observe it (like Heisenberg uncertainty).

```
Example: Race on counter

int count = 0;

Thread A:
  for (int i = 0; i < 1000; i++) {
    count++;  // Read-modify-write, not atomic
  }

Thread B:
  for (int i = 0; i < 1000; i++) {
    count++;
  }

Expected final count: 2000
Actual (50% of runs): 1234, 1567, 1999 (never 2000)

Add logging to debug:
  Thread A: printf("count=%d\n", count++);
  → Now it happens less often (lock contention slows threads down)
  → Might "work" even though bug still exists
  → Heisenbug: Trying to observe it changes the outcome
```

## Finding Concurrency Bugs: TSAN

**ThreadSanitizer (TSAN):** Detects races, deadlocks, data races.

```
C++:
  g++ -fsanitize=thread -g program.cpp -o program
  ./program
  
Output:
  WARNING: ThreadSanitizer: data race (tid=1 vs tid=2)
  Write of size 4 at 0x7fff12345 by thread 1:
    #0 increment() at program.cpp:10
  
  Previous read at 0x7fff12345 by thread 2:
    #0 increment() at program.cpp:10
  
  Locations: shared variable 'count' at program.cpp:5

Java / C++:
  Compile with TSAN → run tests
  TSAN will report data races (even if test passes!)
  → Fix the race before it causes failures
```

## Stress Testing: Making Rare Bugs Reproducible

You have a race condition that happens 1% of the time. How do you make it happen 100% of the time?

**Strategy 1: Schedule Perturbation**

```
Randomize thread scheduling:
  Java: use ThreadLocalRandom, shuffle workload
  C++: sched_setaffinity() to force context switches
  Linux: sysctl kernel.sched_latency_ns = 1000000 (increase context switching)
  
Run test 1000x with different random seeds:
  for i in {1..1000}; do PYTHONHASHSEED=$i python test.py; done
  
Race will likely manifest in 100 runs
```

**Strategy 2: Add Artificial Delays**

```
Insert sleep calls to change relative timing:

Before (no delays):
  Thread A: read count (value 5)
  Thread B: read count (value 5)
  Thread A: write count = 6
  Thread B: write count = 6  ← Both wrote same value!
  
After (with strategic sleep):
  Thread A: read count (value 5)
  Thread A: sleep(1ms)  ← Added delay
  Thread B: read count (value 5)
  Thread A: write count = 6
  Thread B: write count = 6  ← Race is still there, but delayed
  
The delay makes it more likely to manifest.
```

## Common Concurrency Bugs and Detection

**Bug 1: Data Race**

```python
# Thread-unsafe list
items = []

Thread A:
  items.append(1)  # Not atomic

Thread B:
  items.append(2)  # Read-modify-write race

Result: Corrupted list, crash, or silent data loss

Detection:
  TSAN: Will report data race
  Fix: Use Lock or thread-safe data structure
```

**Bug 2: Deadlock**

```python
# Thread A holds Lock1, waiting for Lock2
# Thread B holds Lock2, waiting for Lock1

Thread A:
  with lock1:
    time.sleep(0.1)  # Hold lock1
    with lock2:      # Try to acquire lock2 (blocked!)
      ...

Thread B:
  with lock2:
    time.sleep(0.1)  # Hold lock2
    with lock1:      # Try to acquire lock1 (blocked!)
      ...

Result: Both threads blocked forever

Detection:
  Watchdog timer: If threads don't make progress after 30 sec, report deadlock
  TSAN: Might detect circular lock dependencies
  Dump threads (jstack, gdb bt): See which locks they're waiting for
```

**Bug 3: Use After Free**

```cpp
Thread A:
  delete ptr;  // Free memory

Thread B:
  int val = ptr->field;  // Use after free!

Result: Undefined behavior, crash, memory corruption

Detection:
  ASAN (AddressSanitizer): Detects use-after-free immediately
  Compile: clang++ -fsanitize=address program.cpp
```

**Bug 4: Double-Delete**

```cpp
Thread A:
  delete ptr;  // OK

Thread B (race with A):
  delete ptr;  // Double delete! Heap corruption

Detection:
  ASAN: Detects double-delete and reports it
  TSAN: Might catch the race
```

## Debugging Approach for Concurrency Bugs

**When you suspect a race:**

```
Step 1: Try to reproduce locally
  Run test 100x: for i in {1..100}; do pytest test.py; done
  If it fails, great (reproducible)
  If not, try perturbation (random thread scheduling)

Step 2: Use TSAN to find data races
  Compile with -fsanitize=thread
  Run tests with TSAN
  TSAN reports races (even if test passes)

Step 3: If TSAN is silent but you suspect race
  Add synchronization and see if test passes 100% of time
  Example: Add mutex around shared variable
  If test passes after adding lock → Confirmed race

Step 4: Fix the race
  Option A: Use lock (simple, maybe slow)
  Option B: Use atomic (fast, for simple cases)
  Option C: Redesign to avoid shared state (best, hardest)

Step 5: Verify fix
  Run test 1000x with random seeds
  All pass? → Race is fixed
```

## Interview: Debugging Concurrency Bugs

**Q: "A test fails intermittently on CI but passes locally. What could it be?"**

Weak:
```
"Network issue? Maybe the test is wrong?
Or the CI machine is slow?"
(Guessing, no method)
```

Strong:
```
"Likely a concurrency bug:

1. Local machine might be slower/different timing
   → CI machine faster → different thread scheduling
   → Race manifests on CI but not locally
   
2. Test approach:
   - Try to reproduce locally with stress:
     for i in {1..1000}; do pytest --seed=$i tests.py; done
   
   - Use TSAN:
     Compile with -fsanitize=thread
     Run: TSAN will report data races
   
   - Add locks/synchronization:
     If adding lock makes test always pass → confirmed race
   
3. Fix:
   - Identify shared variable
   - Add proper synchronization (mutex, atomic, etc.)
   - Verify with 1000x test runs

4. Prevent future:
   - Run TSAN on CI (in addition to normal tests)
   - Add stress test (run each test 100x with random seed)
"
```

## Checklist

- [ ] Reproduce locally (or with stress testing)
- [ ] Run with TSAN (or equivalent sanitizer)
- [ ] Identify shared mutable state
- [ ] Add synchronization (lock, atomic, etc.)
- [ ] Verify fix (test passes 1000x)
- [ ] Stress test added to CI (prevent regression)

## Common Mistakes

1. **Adding print statements to debug.** Prints add synchronization (I/O locks), hiding races. Use TSAN instead.
2. **Not using TSAN.** "I'll just add locks everywhere." Inefficient. Use TSAN to find actual races first.
3. **Not reproducing locally.** "It fails on CI, so it's a CI issue." Debug locally with stress testing first.
4. **Fixing a symptom, not the race.** Adding lock in one place without understanding the race → not all races fixed.
5. **Not stress testing after fix.** "Test passes once, so it's fixed." Run 1000x to confirm.

