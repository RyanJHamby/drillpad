# Attribution & Tracing: Finding the Culprit

## Flame Graphs

**Question:** Where does time go?

```
Flame graph:
  x-axis = time (wider = slower)
  y-axis = call stack (higher = deeper in code)
  color = function name

Example:
  main()
    ├─ forward_pass() ← 800ms (wide)
    │   ├─ matmul() ← 600ms (very wide)
    │   └─ activation() ← 200ms
    └─ backward_pass() ← 200ms (narrow)
    
Reading: matmul() is the hotspot (600/1000 = 60% of time)
```

---

## Distributed Tracing

**Question:** Which component is slow in a multi-service system?

```
Request trace:
  Client → API (5ms)
         → Service A (50ms)
         → Service B (100ms) ← SLOW
         → DB (10ms)
         → Response

Root cause: Service B takes 100ms, everything else is fast
```

**Implementation:**

```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Setup
jaeger_exporter = JaegerExporter(agent_host_name="localhost", agent_port=6831)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    trace.export.SimpleSpanProcessor(jaeger_exporter)
)

# Instrument code
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("request") as request_span:
    with tracer.start_as_current_span("service_a") as span_a:
        result_a = service_a.call()
    
    with tracer.start_as_current_span("service_b") as span_b:
        result_b = service_b.call()  # If slow, shows in trace
    
    with tracer.start_as_current_span("database") as span_db:
        result_db = db.query()
```

**Result:** Jaeger UI shows timeline, identifies Service B as bottleneck.

---

## GPU Flight Recorder Example (Your Project)

**Resume claim:** "Replaced per-collective thresholds (0/30 detected) with clock-skew-free block-median lag tests; 30/30 detection"

**Setup:** Distributed GPU training, 8 GPUs. One GPU is slow → entire training slow.

**Without observability:** "Training is slow. Which GPU?" (no idea)

**With observability:**
```python
# Collect NCCL collective timings + NVML metrics
nccl_times = {}  # rank -> [allreduce_times]
nvml_data = {}   # rank -> {temp, throttle, ecc_errors}

for rank in 0..7:
    # NCCL timing
    allreduce_latency = measure_allreduce_time(rank)
    nccl_times[rank].append(allreduce_latency)
    
    # NVML metrics
    nvml_data[rank] = {
        'temp': get_gpu_temp(rank),
        'throttle': get_throttle_reason(rank),
        'ecc': get_ecc_errors(rank)
    }

# Correlate
slow_rank = max(nccl_times.keys(), key=lambda r: nccl_times[r][-1])
cause = nvml_data[slow_rank]

print(f"Rank {slow_rank} is slow: {cause}")
# Output: Rank 3 is slow: temp=90C, throttle=thermal, ecc=0
```

**Clock-skew problem:**
```
GPUs don't have synchronized clocks.

Naive: measure each GPU's allreduce time independently
  GPU 0: measured 100ms
  GPU 1: measured 100ms (but GPU 1's clock is 5ms slower)
  Actual: GPU 1 took 95ms (but measured as 100ms)
  
Solution: Block-median latency test
  All GPUs measure collectively (sync'd start)
  Compare measurements
  Median is most stable (ignores outliers + clock skew)
```

---

## Q&A

**Recall 1:** What's the difference between flame graphs and distributed tracing?

*Must-say:*
- Flame graph: single process, where does time go (function-level)
- Distributed tracing: multi-service, request path (service-level)

**Probe 1:** AllReduce takes 200ms. NVML shows no throttle, ECC=0, temp=65C. Which service is slow?

*Expected:*
- Not the GPU (no throttle, healthy)
- Must be network (AllReduce is collective, all GPUs waiting on network)
- Check network bandwidth, packet loss

---

## Questions for the Interviewer

- How do you identify which rank/GPU is the straggler?
- Do you measure clock skew in distributed systems?
- Have you used distributed tracing in production? (Jaeger, Zipkin?)
