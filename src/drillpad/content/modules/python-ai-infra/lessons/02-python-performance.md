# Python Performance: Profiling, Optimization, Type Hints

## Overview

Python is slower than C++, but profiling and optimization can help:
1. **Profiling tools**: cProfile, py-spy, flamegraph (find hotspots).
2. **Optimization strategies**: Type hints, Numba JIT, vectorization (NumPy).
3. **Production gotchas**: GIL, memory leaks, import costs.

Target: Inference server bottleneck hunting, production debugging.

---

## Profiling: cProfile and py-spy

**Problem:** You know inference is slow, but where?

```python
def infer(prompt):
    embeddings = encode_prompt(prompt)  # ~50 ms?
    scores = score_embeddings(embeddings)  # ~10 ms?
    result = select_top_k(scores, 10)  # ~5 ms?
    return result

# Measure with cProfile
python -m cProfile -s cumulative inference.py
```

**Output (sorted by cumulative time):**
```
   ncalls  tottime  cumtime   %cumtime  function
       10    0.001   52.340    98.0%    infer
       10   50.000   50.001    94.0%    encode_prompt  ← BOTTLENECK
       10    0.100   10.200    19.1%    score_embeddings
       10    0.001    0.050     0.1%    select_top_k
```

**Findings:**
- `encode_prompt` dominates (50 ms out of 53 ms total).
- Optimize this first; others are insignificant.

**Tool 2: py-spy (low-overhead, statistical profiling)**

```bash
pip install py-spy
py-spy record -o profile.svg -- python inference.py
# Captures CPU time distribution, lower overhead than cProfile
```

**Output:** Flamegraph showing call stacks and time spent in each function.

**Interview angle:** How do you profile production code without killing performance?

**Answer:**
- **cProfile:** ~20% overhead, use in staging.
- **py-spy:** ~5% overhead, safe for production (statistical sampling).
- **Custom instrumentation:** Timer probes at key points, log to metrics backend.

---

## Type Hints and JIT Compilation

**Problem:** Python is interpreted; loops are slow.

```python
# Slow: Python interpreter does dynamic type checking at each iteration
def matrix_multiply(A, B):
    C = [[0 for _ in range(len(B[0]))] for _ in range(len(A))]
    for i in range(len(A)):
        for j in range(len(B[0])):
            for k in range(len(B)):
                C[i][j] += A[i][k] * B[k][j]
    return C

# Benchmark: 512x512 matrix mult → ~5 seconds (interpreted)
```

**Solution 1: NumPy (vectorized)**

```python
import numpy as np

A = np.random.randn(512, 512)
B = np.random.randn(512, 512)
C = A @ B  # Matrix multiply in C (NumPy/BLAS)

# Benchmark: ~10 ms (500x faster, compiled C code)
```

**Solution 2: Numba JIT (just-in-time compilation)**

```python
from numba import jit

@jit(nopython=True)  # Compile to native code, no Python fallback
def matrix_multiply_fast(A, B):
    n, m, p = A.shape[0], B.shape[0], B.shape[1]
    C = np.zeros((n, p))
    for i in range(n):
        for j in range(p):
            for k in range(m):
                C[i][j] += A[i][k] * B[k][j]
    return C

# First call: ~1 second (JIT compilation)
# Second call: ~15 ms (compiled code runs at near-C speed)
```

**Type hints enable optimizations:**

```python
from typing import List
import numpy as np

# Type hints help both humans and tools (mypy, Pydantic)
def process_batch(prompts: List[str]) -> np.ndarray:
    """Process batch of prompts, return embeddings."""
    embeddings: np.ndarray = model.encode(prompts)
    return embeddings  # Type checker knows it's ndarray

# Type hints don't speed up runtime, but they:
# 1. Enable static analysis (catch bugs early)
# 2. Help with code clarity
# 3. Enable JIT compiler to specialize (in some cases)
```

**Solution 3: Cython (Python with C types)**

```cython
# multiply.pyx (Cython code)
cimport numpy as np
import numpy as np

def matrix_multiply_cython(double[:, ::1] A, double[:, ::1] B):
    """Matrix multiply with typed arrays."""
    cdef int n = A.shape[0], m = A.shape[1], p = B.shape[1]
    cdef np.ndarray[double, ndim=2] C = np.zeros((n, p))
    cdef int i, j, k
    
    for i in range(n):
        for j in range(p):
            for k in range(m):
                C[i, j] += A[i, k] * B[k, j]
    return C

# Compile: cython multiply.pyx && cc -c multiply.c
# Use: python -c "from multiply import matrix_multiply_cython"
# Benchmark: ~20 ms (compiled, but less optimized than NumPy)
```

**Comparison:**

```
Pure Python:     5000 ms
Numba JIT:         15 ms (333x faster)
NumPy:             10 ms (500x faster)
Cython:            20 ms (250x faster)
C (baseline):       5 ms
```

**Rule of thumb:**
- **I/O-bound** (network, disk): Python is fine, use asyncio.
- **CPU-bound with libraries:** Use NumPy/PyTorch (pre-compiled).
- **CPU-bound custom code:** Use Numba JIT.
- **Extreme performance:** Use Cython or C extension.

---

## Memory Profiling and GIL

**Problem 1: Memory leaks**

```python
cache = {}

def process_request(prompt: str) -> str:
    # BAD: cache grows unbounded
    if prompt not in cache:
        result = expensive_inference(prompt)
        cache[prompt] = result  # Memory leak if not evicted
    return cache[prompt]

# After 1M requests, cache is 1M entries, 1+ GB of memory

# GOOD: bounded cache (LRU)
from functools import lru_cache

@lru_cache(maxsize=10000)
def process_request(prompt: str) -> str:
    return expensive_inference(prompt)
```

**Profiling memory:**

```bash
python -m memory_profiler inference.py
```

Output: Memory usage per line.

**Problem 2: GIL (Global Interpreter Lock)**

```python
import threading

counter = 0

def increment_1m_times():
    global counter
    for _ in range(1000000):
        counter += 1

# Single-threaded
threads = [threading.Thread(target=increment_1m_times) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()

print(counter)  # Expected: 4M. Actual: ~1.5M (GIL prevents true parallelism)
```

**Why:** Python's GIL ensures that only one thread executes Python code at a time. Multiple threads don't help CPU-bound work.

**Solutions:**
- **Use asyncio:** Single thread, 1000s of concurrent I/O operations.
- **Use multiprocessing:** Separate processes, no shared GIL.
- **Use PyPy or other implementations:** PyPy has a different GIL model.
- **Offload to C:** Use NumPy, PyTorch, or C extensions (they release the GIL).

---

## Story Card: Embedding Bottleneck in a Speech-Inference Server

**Setup (illustrative numbers):** A speech-emotion inference server, ~1000 concurrent requests/sec. Each request encodes speech to embeddings (model.encode() is NumPy-based, takes ~100 ms per request).

**Problem:** Single-threaded asyncio, but embedding step is CPU-bound. Event loop is blocked for 100 ms per request.

**Diagnosis:**
```python
# cProfile shows:
# 50% time in model.encode() (numpy operations, releases GIL)
# 50% time in request parsing (Python code, holds GIL)

# py-spy flamegraph confirms: model.encode() is concurrent (multiple stacks),
# but request parsing is serial (one stack at a time).
```

**Fix:** Use request batching + asyncio.

```python
# Batch embedding requests (amortizes kernel launch cost)
async def embed_batch(prompts: List[str]) -> List[np.ndarray]:
    # model.encode() is ~100ms for 1 request, ~105ms for 32 requests (parallel on GPU/CPU)
    return await loop.run_in_executor(
        executor,
        model.encode,
        np.array(prompts)
    )

# Batch many requests at once
batch_queue = asyncio.Queue(maxsize=32)

async def batch_worker():
    while True:
        batch = []
        while len(batch) < 32:
            try:
                prompt = await asyncio.wait_for(batch_queue.get(), timeout=0.05)
                batch.append(prompt)
            except asyncio.TimeoutError:
                break
        
        if batch:
            embeddings = await embed_batch(batch)
            # Return results
```

**Result:**
- Before: 1000 req/s, 100 ms latency each → 100 seconds total time.
- After: 1000 req/s, 105 ms latency per batch of 32 → 3 seconds total time (30x improvement).

---

## Production Gotchas

### Gotcha 1: Import Costs

```python
# inference.py
import torch  # Takes ~2 seconds (initialization)
import transformers  # Takes ~1 second

# Server startup: 3 seconds before handling first request

# SOLUTION: Lazy import in handler
def handler(request):
    global model
    if model is None:
        import torch
        model = torch.load("model.pt")  # Load on first request
    return model.infer(request.prompt)
```

### Gotcha 2: Subprocess Overhead

```python
import subprocess

# BAD: spawn subprocess for each request
def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

# For 1000 req/s, spawning 1000 processes = OS scheduler thrashing

# GOOD: reuse process
import asyncio
process = await asyncio.create_subprocess_shell(cmd)  # Reusable
stdout, _ = await process.communicate()
```

### Gotcha 3: Pickling Overhead

```python
# BAD: serialize/deserialize on every call
def infer_multiprocess(prompts):
    with multiprocessing.Pool(4) as pool:
        results = pool.map(infer_single, prompts)  # Each call pickles argument
    return results

# Pickling is slow (100+ us per object)

# GOOD: use shared memory or queue
import numpy as np
from multiprocessing import Queue

shared_array = np.zeros((1000, 512))  # Shared memory
queue = Queue()
for result in results:
    queue.put(result)  # One pickling cost
```

---

## Q&A

**Recall 1:** What does the GIL do, and why does it matter?

*Must-say:*
- GIL (Global Interpreter Lock): Only one thread executes Python code at a time.
- For I/O-bound: Not a problem (use asyncio or threading, both work).
- For CPU-bound: Threading is useless (GIL serializes); use multiprocessing or PyPy.

**Probe 1:** You profile an inference server and find that 80% of time is in NumPy matmul, 20% in Python request parsing. You add 4 worker threads. Does throughput increase?

*Expected:*
- NumPy matmul releases GIL (C code), so those operations can be concurrent.
- But request parsing holds GIL, serializing the Python work.
- Threads help a little, but GIL still limits throughput.
- Better solution: Use asyncio or separate processes.

**Probe 2:** You use Numba JIT to compile a hot function. The first call is slow (compilation), second call is fast. How do you avoid the first-call slowdown in production?

*Expected:*
- Warm up the JIT during server startup: call the function once with dummy data.
- Or use `@jit(cache=True)` to cache compiled code across runs (Python 3.8+).
- Or pre-compile to shared library using Numba AOT (ahead-of-time).

**Numeric 1:** A request takes 10 ms to parse (Python, GIL), 100 ms to infer (NumPy, releases GIL). With 4 threads, what's the throughput?

*Working:*
- Parse is serial: 10 ms * 4 requests = 40 ms (GIL limits to 1 at a time, sort of).
- Actually, context switching makes it worse: ~50 ms total parse time for 4 requests.
- Infer is concurrent: 100 ms (all 4 run in parallel, NumPy releases GIL).
- Total: 50 + 100 = 150 ms for 4 requests = 37.5 req/s.

**Numeric 2:** cProfile shows function A takes 50 ms, function B takes 3 ms, function C takes 2 ms. You optimize B to take 1 ms (3x faster). What's the total improvement?

*Working:*
- Before: 50 + 3 + 2 = 55 ms.
- After: 50 + 1 + 2 = 53 ms.
- Improvement: 2 / 55 ≈ 3.6% (B is not the bottleneck, so optimizing it has little impact).
- Lesson: Optimize A (the bottleneck).

---

## Questions for the Interviewer

- Do you use Numba, Cython, or compiled extensions for performance?
- How do you handle CPU-bound vs I/O-bound workloads differently?
- Have you hit GIL contention issues? How did you solve them?
- How do you profile and monitor production inference servers?
