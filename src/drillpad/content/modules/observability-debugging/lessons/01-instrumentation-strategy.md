# Instrumentation Strategy: What to Measure

## Measurement Hierarchy

```
Level 1: Application Metrics
  - Request count, latency, errors
  - Example: "1000 req/s, P50 100ms, P99 500ms"

Level 2: System Metrics
  - CPU, memory, disk, network
  - Example: "CPU 60%, memory 8GB, network 500 Mbps"

Level 3: Hardware Counters
  - CPU cycles, cache misses, instructions
  - Example: "2B cycles, 500M L3 misses, 400M instructions"

Level 4: Hardware-Specific
  - GPU: NVML (throttling, ECC, temperature, power)
  - Network: packet loss, latency, queue depth
  - Example: "GPU throttled 2%, ECC errors 0, temp 65C"
```

**Strategy:** Measure all 4 levels, correlate.

---

## NVML (GPU Metrics)

```python
import pynvml

pynvml.nvmlInit()
device = pynvml.nvmlDeviceGetHandleByIndex(0)

# GPU utilization
util = pynvml.nvmlDeviceGetUtilizationRates(device)
print(f"GPU util: {util.gpu}%")  # 0-100

# Memory
mem = pynvml.nvmlDeviceGetMemoryInfo(device)
print(f"Memory: {mem.used / 1e9} GB used")

# Temperature
temp = pynvml.nvmlDeviceGetTemperature(device, 0)
print(f"Temp: {temp}C")

# Power
power = pynvml.nvmlDeviceGetPowerUsage(device)
print(f"Power: {power / 1000}W")

# Throttle reasons
throttle = pynvml.nvmlDeviceGetCurrentThrottleReasons(device)
print(f"Throttled: {throttle}")  # Bit flags for thermal, power, sync boost, etc.

# ECC errors
ecc = pynvml.nvmlDeviceGetTotalEccErrors(device, 0)  # 0 = single-bit
print(f"ECC errors (single-bit): {ecc}")
```

---

## NCCL Metrics (Collective Operations)

```python
import torch
import torch.nn as nn
import torch.distributed as dist

# Start collective timing
start = time.time()

# AllReduce (sum gradients across GPUs)
dist.all_reduce(gradients, op=dist.ReduceOp.SUM)

elapsed = time.time() - start
print(f"AllReduce time: {elapsed * 1000} ms")

# Bandwidth utilization
data_moved = gradients.numel() * 4 * 2  # bytes * 2 (reduce + scatter)
bw_utilization = (data_moved / (elapsed * 1e9)) / 900  # NVLink is 900 GB/s
print(f"Bandwidth utilization: {bw_utilization * 100}%")
```

---

## Hardware Counters (perf)

```bash
# CPU cycles, instructions, cache misses
perf stat -e cycles,instructions,cache-references,cache-misses ./app

# Output:
# Performance counter stats for './app':
# 10,000,000,000 cycles
# 5,000,000,000 instructions (0.5 IPC)
# 1,000,000 cache-references
# 500,000 cache-misses (50% miss rate)
```

---

## Correlating Metrics: The Bottleneck Chain

```
GPU Training Loop

Metrics over time:
  GPU util: 100% → 10% → 100%
  AllReduce time: 10ms → 200ms → 10ms
  Network bandwidth: 900GB/s → 100GB/s → 900GB/s
  
Observation: GPU util drops when allreduce is slow
Conclusion: Network is bottleneck during allreduce
```

---

## Q&A

**Recall 1:** What's the difference between NVML and hardware counters?

*Must-say:*
- NVML: GPU-specific (throttling, temperature, power)
- Hardware counters: CPU-level (cycles, cache misses)
- Both needed for full picture

**Probe 1:** GPU util 100%, AllReduce 200ms. Which is the bottleneck?

*Expected:*
- GPU is saturated
- AllReduce is slowing GPU down
- Root cause: network, not GPU compute

---

## Questions for the Interviewer

- Which metrics do you monitor in production? (GPU temp, ECC errors?)
- How do you avoid overhead from too much instrumentation?
- Do you use sampling (1% of requests) or full coverage?
