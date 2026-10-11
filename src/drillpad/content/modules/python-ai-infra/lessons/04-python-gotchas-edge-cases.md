# Python Gotchas & Edge Cases: Mutable Defaults, Iterators, Late Binding, GIL

## Overview

Python has many subtle traps that can cause bugs or terrible performance. Interview gotchas:
1. **Mutable default arguments:** Shared across calls.
2. **Iterators and generators:** Lazy evaluation, state.
3. **Late binding in closures:** Variables bound at call time, not definition time.
4. **GIL surprises:** Threading doesn't parallelize CPU-bound work.
5. **Type hints:** Don't enforce at runtime.

---

## Mutable Default Arguments

**The gotcha:**

```python
def add_request(request, queue=[]):  # [] is created ONCE at function definition
    queue.append(request)
    return queue

r1 = add_request("req1")
print(r1)  # ['req1']

r2 = add_request("req2")
print(r2)  # ['req1', 'req2']  ← SURPRISING!

# The list is SHARED across all calls!
# It's created once when Python parses the function definition.
```

**Why it happens:**

```python
# This is how Python evaluates default arguments
def func(x=[]):
    pass

# Equivalent to:
_default_list = []
def func(x=_default_list):
    pass

# The default list is created ONCE, reused for all calls.
```

**Fix:**

```python
def add_request(request, queue=None):
    if queue is None:
        queue = []
    queue.append(request)
    return queue

r1 = add_request("req1")
print(r1)  # ['req1']

r2 = add_request("req2")
print(r2)  # ['req2']  ← Correct
```

**Interview gotcha:** "What's wrong with this function?"

```python
def batch_requests(requests, db_cache={}):
    for req in requests:
        if req not in db_cache:
            db_cache[req] = expensive_fetch(req)
    return db_cache
```

**Answer:** The cache is shared across all calls. After the first call, all subsequent calls reuse the old cache (which is probably not what you want for a real cache, or it's a memory leak if callers expect fresh caches).

---

## Iterators and Generators: Lazy Evaluation

**Problem:** Iterators are stateful. Consuming them has side effects.

```python
def get_orders():
    """Generator function (uses yield)."""
    for i in range(5):
        print(f"Fetching order {i}")
        yield Order(id=i)

# Create iterator
orders = get_orders()

# Iterate (side effects happen here, not at creation)
for o in orders:
    print(f"Processing {o.id}")

# Output:
# Fetching order 0
# Processing 0
# Fetching order 1
# Processing 1
# ...

# Gotcha: If you iterate again, nothing happens (iterator exhausted)
for o in orders:
    print(o)  # No output! Iterator is consumed.

# FIX: Create a new iterator
orders = get_orders()  # Fresh iterator
for o in orders:
    print(o)  # Works
```

**Interview gotcha: Slicing an iterator**

```python
def stream_trades():
    for trade in fetch_all_trades():
        yield trade

trades = stream_trades()

# You want the first 100
first_100 = trades[:100]  # ERROR! Iterators don't support slicing

# FIX: Use itertools
import itertools
first_100 = list(itertools.islice(trades, 100))

# Or: convert to list (loads everything into memory)
first_100 = list(trades)[:100]
```

**When to use generators:**

```python
# Generator: memory-efficient, lazy
def large_dataset():
    for i in range(1000000):
        yield i

for x in large_dataset():
    print(x)  # Only one item in memory at a time

# List: eager, all in memory
data = list(large_dataset())  # 1M integers, ~8 MB memory
```

**Real example: Inference request stream**

```python
# BAD: Load all requests into memory
all_requests = fetch_all_requests()  # 1M requests, huge memory

# GOOD: Stream requests
def request_stream():
    while True:
        req = fetch_next_request()
        if req is None:
            break
        yield req

for req in request_stream():
    batch.append(req)
    if len(batch) == 32:
        results = model.infer(batch)
        batch.clear()
```

---

## Late Binding in Closures

**The gotcha:**

```python
def create_multipliers():
    """Create functions that multiply by 2, 3, 4."""
    multipliers = []
    for i in range(2, 5):
        def mult(x):
            return x * i  # i is LATE-BOUND
        multipliers.append(mult)
    return multipliers

f2, f3, f4 = create_multipliers()

print(f2(10))  # Expected: 20. Actual: 40 (i=4)
print(f3(10))  # Expected: 30. Actual: 40 (i=4)
print(f4(10))  # Expected: 40. Actual: 40 (i=4)

# All functions use the SAME i, which is 4 after the loop
```

**Why it happens:**

```python
# Python closures capture variables by reference, not by value.
# When mult() is called, it looks up i in the enclosing scope.
# By then, i=4 (loop is done).

# Equivalent to:
multipliers = []
i = 2
def mult(x):
    return x * i
multipliers.append(mult)

i = 3
def mult(x):
    return x * i
multipliers.append(mult)

i = 4
def mult(x):
    return x * i
multipliers.append(mult)

# All refer to the same i variable
```

**Fix: Capture by value**

```python
def create_multipliers():
    multipliers = []
    for i in range(2, 5):
        def mult(x, i=i):  # Default argument captures i by value
            return x * i
        multipliers.append(mult)
    return multipliers

f2, f3, f4 = create_multipliers()
print(f2(10))  # 20 (correct)
print(f3(10))  # 30 (correct)
print(f4(10))  # 40 (correct)
```

**Or use a factory:**

```python
def make_multiplier(n):
    def mult(x):
        return x * n
    return mult

multipliers = [make_multiplier(i) for i in range(2, 5)]
# Each closure captures a different n
```

**Interview gotcha: Event handlers**

```python
buttons = []
for i in range(5):
    def onclick():
        print(f"Button {i} clicked")
    buttons.append(onclick)

# When you click button 0, it prints "Button 4 clicked"
# Because i is late-bound (all refer to i=4 after the loop)

# FIX:
for i in range(5):
    def onclick(i=i):
        print(f"Button {i} clicked")
    buttons.append(onclick)
```

---

## Type Hints: They Don't Enforce at Runtime

**The gotcha:**

```python
def process_batch(requests: List[Request]) -> List[Result]:
    """Type hints say requests is a List[Request]."""
    return [infer(r) for r in requests]

# But Python doesn't check at runtime!
process_batch("not a list")  # No error (until you try to iterate)

# Type hints are for static analysis (mypy, IDE autocompletion)
# NOT for runtime validation
```

**Why it matters in production:**

```python
@app.post("/infer")
async def infer(request: Request) -> Response:
    # request is type-hinted as Request
    # But the HTTP framework deserializes it from JSON
    # If JSON is malformed, you get a dict, not a Request object
    
    # Type hint doesn't prevent this!
    # FIX: Use Pydantic for validation
    from pydantic import BaseModel
    
    class InferRequest(BaseModel):
        prompt: str
        temperature: float = 0.7
    
    @app.post("/infer")
    async def infer(request: InferRequest) -> Response:
        # Pydantic validates at runtime
        # If JSON doesn't match schema, 422 error
```

**Performance: Type hints have zero cost**

```python
def sum_numbers(nums: List[int]) -> int:
    return sum(nums)

# Type hints don't slow down runtime
# They're metadata (available in __annotations__)
print(sum_numbers.__annotations__)  # {'nums': List[int], 'return': int}

# But they help with:
# 1. IDE autocompletion
# 2. Static analysis (mypy)
# 3. Code documentation
```

---

## GIL Surprises

**The gotcha: Threading doesn't parallelize CPU-bound work**

```python
import threading
import time

def cpu_bound():
    total = 0
    for i in range(100000000):
        total += i
    return total

start = time.time()
cpu_bound()
print(f"Single-threaded: {time.time() - start:.2f}s")

# Now with threading
start = time.time()
t1 = threading.Thread(target=cpu_bound)
t2 = threading.Thread(target=cpu_bound)
t1.start()
t2.start()
t1.join()
t2.join()
print(f"Two threads: {time.time() - start:.2f}s")  # Same or SLOWER!
```

**Why:**
- GIL (Global Interpreter Lock) prevents two threads from executing Python code simultaneously.
- Context switching overhead makes threading slower than single-threaded.

**Solutions:**

```python
# 1. Use multiprocessing (separate processes, no GIL)
from multiprocessing import Pool
with Pool(2) as p:
    results = p.map(cpu_bound, range(2))

# 2. Use asyncio for I/O-bound work (not CPU-bound)
async def io_bound():
    await asyncio.sleep(1)  # I/O releases GIL

# 3. Offload to C (NumPy, PyTorch, compiled extensions)
import numpy as np
A = np.random.randn(1000, 1000)
B = np.random.randn(1000, 1000)
C = A @ B  # C code, releases GIL
```

**Interview gotcha:** "I spawned 4 threads to parallelize work. Why is it 4x slower?"

**Answer:** You're doing CPU-bound work with threading. Use multiprocessing or asyncio instead. Threading is only for I/O-bound.

---

## Story Card: Cache Deduplication Problem

**Setup:** A phone-screen style problem. Implement a cache in front of a slow service. Multiple concurrent requests for the same key should be deduplicated (only one hits the backend; others wait for the result).

**Problem:**

```
Thread A: cache.get("user:123")  → MISS, hits slow backend (100 ms)
Thread B: cache.get("user:123")  → should wait for A's result, not hit backend again
Thread C: cache.get("user:456")  → MISS, hits backend (concurrent, independent)

Results:
  A and B return same result (fetched once)
  C returns independent result
  Total backend calls: 2 (not 3)
```

**Solution: Request deduplication with in-flight tracking**

```python
import asyncio
from typing import Dict, Any

class DedupCache:
    def __init__(self, ttl_seconds: int = 60):
        self.cache: Dict[str, Any] = {}  # Cached results
        self.in_flight: Dict[str, asyncio.Future] = {}  # Pending requests
        self.ttl = ttl_seconds
    
    async def get(self, key: str) -> Any:
        """Get value from cache, dedup concurrent requests to backend."""
        
        # Check cache first
        if key in self.cache:
            return self.cache[key]
        
        # Check if request is already in-flight
        if key in self.in_flight:
            # Wait for the in-flight request to complete
            result = await self.in_flight[key]
            return result
        
        # Create a new future for this request
        future: asyncio.Future[Any] = asyncio.Future()
        self.in_flight[key] = future
        
        try:
            # Fetch from slow backend (only one thread does this)
            result = await self.fetch_from_backend(key)
            
            # Cache and resolve future
            self.cache[key] = result
            future.set_result(result)
            
            return result
        except Exception as e:
            # If backend fails, all waiters see the exception
            future.set_exception(e)
            raise
        finally:
            # Clean up in-flight tracking
            self.in_flight.pop(key, None)
    
    async def fetch_from_backend(self, key: str) -> Any:
        """Slow backend fetch (100+ ms)."""
        # Simulate slow service
        await asyncio.sleep(0.1)
        return f"result_for_{key}"

# Usage
cache = DedupCache()

async def concurrent_requests():
    """Three concurrent requests: two for same key, one different."""
    # Thread A and B request same key, C requests different key
    results = await asyncio.gather(
        cache.get("user:123"),  # Hits backend
        cache.get("user:123"),  # Waits for A's result
        cache.get("user:456"),  # Hits backend (concurrent)
    )
    return results

# Result: 2 backend calls, 3 results returned
```

**Interview follow-ups:**
- Q: "What if the backend times out?"
  - A: Set a timeout on `fetch_from_backend()`. If it times out, exception propagates to all waiters.
- Q: "What about cache invalidation?"
  - A: Add TTL: periodically evict entries older than ttl_seconds. Or use a `cache_for` timestamp.
- Q: "What if the same key is requested again after cache expires?"
  - A: Automatically refetch (same dedup logic applies).
- Q: "How do you handle partial failures?"
  - A: If one waiter cancels its task, others still wait. If backend fails, all see the exception and can retry independently.

**Why this pattern matters:**
- Real example: Let's Encrypt certificate validation (1000 clients request same cert, only one hits validation backend).
- Also: Database connection pools, API rate limiting, expensive computations (ML inference).

---

## Q&A

**Recall 1:** What's wrong with using a mutable default argument?

*Must-say:*
- Default arguments are created once at function definition, shared across all calls.
- Use None and create a new object each call.

**Probe 1:** You have a generator that yields 1000 items. A caller consumes 10, then calls the generator again. What happens?

*Expected:*
- The generator is exhausted (stateful).
- The caller gets nothing the second time.
- FIX: Create a new generator each time, or use itertools.tee to cache results.

**Probe 2:** You have a closure that captures a loop variable. All functions see the same variable. How do you fix it?

*Expected:*
- Use a default argument to capture by value: `def f(i=i)`.
- Or use a factory function.
- Or use itertools.partial.

**Numeric 1:** You have a cache with dedup. 100 concurrent requests: 60 for key "A", 40 for key "B". Backend time is 100 ms per key. How many backend calls, and what's the total time?

*Working:*
- Backend calls: 2 (one for "A", one for "B"). All 100 requests deduplicate to these two.
- Time: max(100 ms, 100 ms) = 100 ms (both keys are fetched in parallel).
- If requests were sequential: 100 * 100 ms = 10 seconds.

**Numeric 2:** You spawn 4 threads to parallelize CPU-bound work. Each thread does 1 second of work. How long does it take?

*Working:*
- Single-threaded: 4 seconds.
- Four threads with GIL: ~4 seconds (maybe 4.5 with overhead), NOT 1 second.
- (GIL prevents parallelism, threading adds context switch overhead.)

---

## Questions for the Interviewer

- How do you handle mutable default arguments in your codebase (linting, code review)?
- Have you hit any late-binding closure bugs?
- How do you validate input types at runtime (Pydantic, dataclasses, manual)?
- Do you use threading for CPU-bound work, and why or why not?
