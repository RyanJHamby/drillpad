# Async Inference Patterns: Batching, Backpressure, Graceful Shutdown

## Overview

Production inference servers combine asyncio + batching to maximize GPU utilization while handling 1000s of concurrent requests:
1. **Request batching:** Collect requests, run inference on batch.
2. **Backpressure:** Limit queue depth to prevent memory bloat.
3. **Graceful shutdown:** Drain pending requests, cancel tasks cleanly.

Real context: vLLM, speech-emotion inference, feature-serving platforms.

---

## Request Batching Pattern

**Problem:** Inference has fixed overhead (GPU kernel launch ~2 ms). Single requests waste this.

```python
# Bad: process requests one by one
async def infer_single(prompt: str) -> str:
    return await model.generate(prompt)  # 100 ms per request

# For 100 concurrent requests:
# - GPU utilization: 10% (90% wasted on kernel launches)
# - Throughput: 1000 / 100 = 10 req/s
```

**Solution: Batch requests**

```python
import asyncio
from typing import List

request_queue = asyncio.Queue()
batch_size = 32
batch_timeout = 0.05  # 50 ms

async def request_handler(prompt: str) -> asyncio.Future:
    """HTTP handler: enqueue request and return future for result."""
    future = asyncio.Future()
    await request_queue.put((prompt, future))
    return future

async def batch_inference_worker():
    """Collect requests into batches, run inference."""
    while True:
        batch_prompts = []
        batch_futures = []
        
        # Collect batch (up to batch_size or timeout)
        try:
            while len(batch_prompts) < batch_size:
                prompt, future = await asyncio.wait_for(
                    request_queue.get(),
                    timeout=batch_timeout
                )
                batch_prompts.append(prompt)
                batch_futures.append(future)
        except asyncio.TimeoutError:
            pass
        
        if batch_prompts:
            # Run inference on batch (GPU-efficient)
            try:
                results = await model.generate_batch(batch_prompts)
                # Return results to clients
                for future, result in zip(batch_futures, results):
                    future.set_result(result)
            except Exception as e:
                # If batch fails, notify all clients
                for future in batch_futures:
                    future.set_exception(e)

# HTTP endpoint
from fastapi import FastAPI
app = FastAPI()

@app.post("/infer")
async def infer(prompt: str):
    future = await request_handler(prompt)
    result = await future  # Wait for batch to complete
    return {"result": result}

# Start batch worker
asyncio.create_task(batch_inference_worker())
```

**Analysis:**

```
Without batching:
  100 requests, 100 ms each (sequential) → 10 seconds total
  
With batching (batch_size=32):
  100 requests, grouped into 3 batches
  Batch 1 (32 reqs): 100 ms
  Batch 2 (32 reqs): 100 ms
  Batch 3 (36 reqs): 100 ms
  Total: 300 ms (30x faster!)
  
  P99 latency:
    - Without: 100 ms * 100 = 10 seconds
    - With batching: max(100 ms for batching + timeout) ≈ 50 ms per batch
```

**Interview angle:** What's the tradeoff between batch_size and latency?

**Answer:**
- **Large batch_size (e.g., 128):** Higher throughput, higher latency (longer wait for batch to fill).
- **Small batch_size (e.g., 8):** Lower latency, lower throughput (more kernel launches).
- **Timeout:** Ensures latency SLO (e.g., 50 ms timeout = no request waits > 50 ms).

---

## Backpressure and Flow Control

**Problem:** If producer is much faster than consumer, queue grows unbounded → OOM.

```python
# Without backpressure
request_queue = asyncio.Queue()  # Unbounded

async def producer():
    for i in range(1000000):
        await request_queue.put(f"request_{i}")  # Never blocks
        # Queue grows to 1M items, consuming GBs of RAM

# With backpressure
request_queue = asyncio.Queue(maxsize=1000)  # Bounded

async def producer():
    for i in range(1000000):
        await request_queue.put(f"request_{i}")  # Blocks if queue is full
        # Queue maxes at 1000 items, memory bounded
        # Producer pauses until consumer drains queue
```

**Monitoring queue depth (for autoscaling):**

```python
request_queue = asyncio.Queue(maxsize=1000)

async def monitor_queue():
    while True:
        depth = request_queue.qsize()
        print(f"Queue depth: {depth}")
        
        # Alert if approaching limit
        if depth > 900:
            print("WARNING: Queue is full, consider scaling up")
        
        # Metrics for autoscaler
        metrics.gauge("request_queue_depth", depth)
        
        await asyncio.sleep(1)

asyncio.create_task(monitor_queue())
```

**Autoscaling logic:**

```python
# If queue depth > 900 for 5 seconds, spawn more workers
queue_depth_history = []

async def autoscaler():
    while True:
        depth = request_queue.qsize()
        queue_depth_history.append(depth)
        
        # Check last 5 seconds
        if len(queue_depth_history) > 5:
            queue_depth_history.pop(0)
        
        if all(d > 900 for d in queue_depth_history):
            print("Queue sustained > 900 for 5s, scaling up")
            spawn_worker()  # Start another batch worker
        
        await asyncio.sleep(1)
```

**Interview angle:** How do you prevent a slow consumer from causing the producer to block?

**Answer:**
- Use a bounded queue with backpressure.
- Scale consumers dynamically based on queue depth.
- Consider shedding load (reject requests if queue is full) instead of blocking indefinitely.

---

## Graceful Shutdown

**Problem:** If you kill the server mid-request, pending requests are lost.

```python
# Bad: abrupt shutdown
async def main():
    worker_task = asyncio.create_task(batch_inference_worker())
    # ... run for a while ...
    # Server dies, pending requests are lost
```

**Graceful shutdown pattern:**

```python
import signal

shutdown_event = asyncio.Event()

async def shutdown_handler(sig):
    """Signal handler for SIGTERM (graceful shutdown)."""
    print(f"Received signal {sig}, initiating graceful shutdown")
    shutdown_event.set()  # Signal all tasks to stop

async def batch_inference_worker():
    """Drain pending requests on shutdown."""
    while not shutdown_event.is_set():
        # Same as before: collect and process batch
        batch_prompts = []
        batch_futures = []
        
        try:
            while len(batch_prompts) < batch_size:
                prompt, future = await asyncio.wait_for(
                    request_queue.get(),
                    timeout=batch_timeout
                )
                batch_prompts.append(prompt)
                batch_futures.append(future)
        except asyncio.TimeoutError:
            pass
        
        if batch_prompts:
            results = await model.generate_batch(batch_prompts)
            for future, result in zip(batch_futures, results):
                future.set_result(result)
    
    # After shutdown event, drain remaining requests
    print("Draining pending requests")
    while not request_queue.empty():
        try:
            prompt, future = request_queue.get_nowait()
            # Process final batch
            result = await model.generate(prompt)
            future.set_result(result)
        except asyncio.QueueEmpty:
            break
    
    print("Graceful shutdown complete")

async def main():
    # Register signal handlers
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown_handler(signal.SIGTERM)))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown_handler(signal.SIGINT)))
    
    worker_task = asyncio.create_task(batch_inference_worker())
    
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

**Docker/Kubernetes integration:**

```dockerfile
# Dockerfile
FROM python:3.11
COPY server.py .
CMD ["python", "server.py"]

# In server.py:
# - Register signal handlers (SIGTERM, SIGINT)
# - Drain queue on shutdown (max 30 seconds)
# - Return HTTP 503 (Service Unavailable) after shutdown event
```

**Health checks (Kubernetes readiness/liveness):**

```python
@app.get("/health")
async def health_check():
    """Readiness probe: return 200 if serving, 503 if shutting down."""
    if shutdown_event.is_set():
        raise HTTPException(status_code=503, detail="Shutting down")
    
    # Also check queue depth (circuit breaker)
    if request_queue.qsize() > max_queue_depth:
        raise HTTPException(status_code=503, detail="Queue full")
    
    return {"status": "healthy"}

# Kubernetes will:
# - Use /health to detect when pod is ready
# - Send SIGTERM on pod termination, wait 30s for graceful shutdown
# - Force kill if not done in 30s (grace period)
```

---

## Story Card: vLLM Batching in Production

**Setup:** vLLM serving Llama-70B, ~500 concurrent users (GPT API compatible).

**Initial design:** No batching, one request per GPU forward pass. GPU utilization: 30% (many requests are short, 10 tokens). P99 latency: 8 seconds (waiting for GPU).

**Redesign:** Continuous batching (vLLM's original innovation).

```python
# Continuous batching:
# - New request arrives: add to batch
# - Request finishes early (short): keep batch slot, reuse for next request
# - GPU runs continuously (100% utilization)

batch_slots = 64  # 64 request slots in batch
active_requests: Dict[int, Request] = {}

async def add_request(request: Request):
    request_id = next_request_id()
    active_requests[request_id] = request
    
    # Allocate KV-cache for this request (1 GB for 4K context)
    # As request finishes, deallocate and reuse

async def continuous_batch_worker():
    while True:
        # Run prefill on new requests, decode on existing
        batch = []
        for req_id, request in list(active_requests.items()):
            if request.is_finished():
                active_requests.pop(req_id)
            else:
                batch.append(request)
        
        if batch:
            # GPU forward pass on batch
            output = await model.forward(batch)
            
            # Update requests with new tokens
            for i, request in enumerate(batch):
                request.add_token(output[i])
                if request.is_finished():
                    request.resolve_future()
```

**Result:**
- Before: 30% GPU utilization, P99 8s.
- After: 90% GPU utilization, P99 300 ms (25x improvement).

**Why:** Batching amortizes GPU overhead (kernel launch, memory I/O) across many requests. Continuous batching allows requests to finish early without stalling the batch.

---

## Q&A

**Recall 1:** What's the difference between batching and continuous batching?

*Must-say:*
- **Batching:** Collect N requests, run inference, return all results. Latency = batch collection time + inference time.
- **Continuous batching:** Process requests continuously; as one finishes, remove from batch and add new request. Higher utilization, lower latency.

**Probe 1:** You have a batch timeout of 50 ms. Requests arrive at 10 req/s, batch size 32. What's the average batch size?

*Expected:*
- 10 req/s * 50 ms timeout = 0.5 requests collected by timeout.
- Expected batches: 10 req/s / 32 = 0.3125 batches/s (one batch every 3.2 seconds).
- Actually, batches fill when 32 requests arrive, then timeout=irrelevant.
- At 10 req/s, it takes 3.2 seconds to fill a batch of 32.
- So either timeout hits (small batch), or timeout doesn't matter (batch fills naturally).

**Probe 2:** Graceful shutdown: queue has 100 pending requests, each takes 10 ms. How long to drain?

*Expected:*
- With batch size 32, each batch takes 10 ms.
- 100 requests → 4 batches (32 + 32 + 32 + 4).
- Total: 4 * 10 ms = 40 ms to drain.
- Plus signal propagation, cleanup → ~50 ms total.
- If Kubernetes grace period is 30s, plenty of time.

**Numeric 1:** Batch size 32, timeout 50 ms, request rate 100 req/s. Average latency = ?

*Working:*
- Batch fills in: 32 / 100 req/s = 320 ms (requests arrive at 100 req/s, batch ready after 320 ms).
- No wait, that's backwards. 100 req/s = 10 ms per request on average.
- 32 requests arrive in: 32 * 10 ms = 320 ms. No, 32 requests at 100 req/s = 320 ms? No: 100 req/s means 1 req per 10 ms, so 32 reqs = 320 ms.
- Actually simpler: at 100 req/s, we have 100/32 ≈ 3.1 batches per second.
- Each batch processes 32 requests in 100 ms (inference time).
- Average latency = 100 ms / 2 = 50 ms (half the batch inference time, on average).
- Wait, need to include batching delay.
- Average wait in queue: timeout/2 = 25 ms (uniform distribution).
- Inference time: 100 ms.
- Total: 25 + 100 = 125 ms P50 latency.

---

## Questions for the Interviewer

- How do you measure batching efficiency (GPU utilization, throughput)?
- Do you use dynamic batch sizing based on queue depth?
- How long is your graceful shutdown timeout, and how is it tuned?
- Have you hit any issues with request starvation (small batches waiting forever)?
