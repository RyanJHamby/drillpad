# Production Debugging: Low-Overhead Sampling, Post-Hoc Analysis, Root Cause

## Challenge: Measure Without Slowing System

Full instrumentation = overhead that itself becomes the bottleneck.

```
Option 1: Measure everything
  10ms latency request + 5ms instrumentation = 15ms apparent latency
  Overhead: 50% (changes behavior)
  Problem: not representative of production

Option 2: Measure 100% of requests
  Disk I/O for logging: 1TB/day
  Cost: $300/month storage

Option 3: Sample 1% of requests
  Overhead: 0.5ms per request (5% vs 50%)
  Logging: 10GB/day
  Cost: $3/month
```

---

## Sampling Strategy

```python
import random

def should_trace(request_id):
    """Sample 1% of requests."""
    return hash(request_id) % 100 == 0

def process_request(request):
    trace_enabled = should_trace(request.id)
    
    if trace_enabled:
        start_time = time.perf_counter()
        span = create_span(request.id)
    
    result = do_work(request)
    
    if trace_enabled:
        elapsed = time.perf_counter() - start_time
        span.add_attribute("latency_ms", elapsed * 1000)
        span.end()
    
    return result
```

**Benefit:** 1% of requests have full instrumentation, 99% have none.

---

## Tail Latency Sampling (Adaptive)

Problem: Sampling 1% might miss P99 spikes.

```python
def should_trace_adaptive(request_id, latency_ms):
    """Sample 1% normally, 100% of slow requests."""
    
    if latency_ms > 500:  # P99+ threshold
        return True
    
    if hash(request_id) % 100 == 0:
        return True
    
    return False

# In post-processing:
# - Normal requests: 1% sampled
# - Slow requests: 100% sampled
# Result: Full visibility into P99 without overhead
```

---

## Post-Hoc Analysis

**Scenario:** P99 latency spiked to 500ms (normal: 50ms).

**Investigation:**
```
1. Query metrics during spike
   "Request count" histogram by component
   
2. Find anomaly
   AllReduce latency jumped from 10ms to 150ms
   Network bandwidth dropped from 900GB/s to 100GB/s
   
3. Correlate metrics
   AllReduce slow ← network bandwidth low ← network congestion
   
4. Root cause
   Another training job started on same network
   Sharing PCIe bandwidth
   
5. Solution
   Schedule jobs to avoid overlap
   Or: upgrade network (PCIe 4.0 → Infiniband)
```

---

## GPU Flight Recorder: Production Debugging Case Study

**Your resume claim:** "Replaced per-collective thresholds (0/30 detected at 10% jitter) with clock-skew-free block-median lag tests; 30/30 detection and attribution across 9 injected fault types"

**Setup:** 30 fault injections, need to detect all.

**Naive approach (per-collective thresholds):**
```
Monitor each AllReduce independently
  threshold: AllReduce latency > 10ms * 110% = 11ms
  
Test fault: thermal throttle on GPU 3
  Normal allreduce: 10ms
  With throttle: 11.5ms
  Detection: "Slower than 110%?" Yes → detected
  
But: clock skew of 5% means
  GPU 3 clock: measured 11.5ms (actual 10.9ms due to slow clock)
  False positive rate: ~10% jitter = missing 30% of faults
```

**Fixed approach (block-median, clock-skew-aware):**
```python
def detect_straggler(nccl_times, fault_type):
    """
    Detect straggler rank using block-median (clock-skew-immune).
    """
    
    # Measure allreduce times for 10 consecutive collectives
    blocks = [
        [measure_rank_latency(r, i) for r in range(8)]
        for i in range(10)
    ]
    
    # Median across blocks (each rank)
    medians = [
        np.median([blocks[b][r] for b in range(10)])
        for r in range(8)
    ]
    
    # Straggler is max latency
    straggler_rank = np.argmax(medians)
    
    # Attribute cause
    if is_thermally_throttled(straggler_rank):
        return (straggler_rank, "thermal")
    elif is_ecc_error(straggler_rank):
        return (straggler_rank, "ecc")
    else:
        return (straggler_rank, "unknown")

# Test: 30 faults (9 types × ~3 each)
detected = 0
for fault_type in ['thermal', 'ecc', 'nvlink_error', ...]:
    inject_fault(fault_type)
    rank, cause = detect_straggler()
    if rank == faulty_rank and cause == fault_type:
        detected += 1

print(f"Detection rate: {detected}/30 = {detected/30*100}%")
# Output: 30/30 = 100%
```

**Result:** (Your resume) 30/30 detection (vs 0/30 with naive approach).

---

## Q&A

**Recall 1:** Why sample 1% instead of measuring everything?

*Must-say:*
- Sampling: low overhead, captures trends
- Tail sampling: 100% of slow requests, 1% of fast ones
- Full measurement: too expensive, skews results

**Probe 1:** You're debugging a P99 latency spike. You only sampled 1% of requests. Did you capture the spike?

*Expected:*
- Depends on sampling strategy
- If tail sampling: yes (100% of slow requests)
- If uniform sampling: maybe (1% chance)
- Better: adaptive sampling (sample all P99+)

---

## Questions for the Interviewer

- How do you sample production requests without bias?
- Have you had to debug a production incident with limited visibility?
- Do you use post-hoc analysis or always-on instrumentation?
