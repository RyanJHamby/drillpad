# GPU Profiling & NCCL Debugging

## Tools

```
NVML (NVIDIA Management Library):
  Metrics: GPU temp, power, utilization, clock speed
  Usage: real-time monitoring
  
NCCL (NVIDIA Collective Communications Library):
  Debugging: all-reduce latency, bandwidth, ring topology
  Trace: event log per GPU
  
Nsight Systems:
  Profiling: CPU + GPU timeline
  Bottleneck: compute vs memory vs synchronization
  
CUDA Compute Sanitizer:
  Correctness: race conditions, memory errors
  
Torch Profiler (PyTorch):
  Integration: seamless with training code
  Trace: CPU ops, CUDA kernel time
```

---

## Key Metrics

```
Utilization (GPU):
  - Good: >80% (GPU doing work, not waiting)
  - Bad: <50% (GPU idle, bottleneck elsewhere)
  - Measure: nvidia-smi | grep %

Memory:
  - Used: working set size
  - BW: MB/sec (important for memory-bound kernels)
  - Saturation: is memory bandwidth full?
    └─ Roofline: peak BW = 900 GB/sec (A100)
    └─ If actual < 100 GB/sec: compute-bound

Clock Speed:
  - Thermal throttling: temp > 80C → clock down
  - Power limit: hitting max watts
  
NCCL Bandwidth:
  - Ring topology: node-to-node link speed
  - all-reduce latency: sum of link latencies
  - Trace: see which rank (GPU) slow
```

---

## Bottleneck Detection

```
High training loss, slow convergence?

Check 1: GPU idle?
  nvidia-smi shows <20% utilization
  → CPU bottleneck (data loading, preprocessing)
  → Solution: async data pipeline, prefetch batches

Check 2: Data loading time?
  Torch profiler: DataLoader takes 30s/batch, model 5s/batch
  → CPU is slow feeding data
  → Solution: increase num_workers, use SSD instead of NFS

Check 3: GPU memory error?
  CUDA OOM after 100 iterations
  → Memory leak in model or gradient accumulation
  → Solution: profile with Compute Sanitizer, find leak

Check 4: NCCL all-reduce slow?
  Profiler: all-reduce takes 10x expected time
  → Network topology issue (GPU on different NIC)
  → Solution: check ring topology, bind to correct NIC

Check 5: Compute slow?
  Utilization high, but training slow
  → Wrong model, bad hyperparams, or numerical instability
  → Solution: validate model, check loss NaN/Inf
```

---

## NCCL Ring Topology

```
Scenario: 8 GPUs on 2 nodes (4 GPUs each)

Ring order matters:

Bad (cross-network):
  GPU0 (node0) → GPU4 (node1) → GPU1 (node0) → ...
  └─ Hops between nodes: many (network congestion)

Good (locality-aware):
  GPU0 (node0) → GPU1 (node0) → GPU2 (node0) → GPU3 (node0) → 
  GPU4 (node1) → GPU5 (node1) → GPU6 (node1) → GPU7 (node1) → back
  └─ Cross-network: 1 hop, then 1 hop back (efficient)

Detect:
  NCCL_DEBUG=INFO python train.py 2>&1 | grep "ring"
  → Shows ring order

Fix:
  NCCL_DEBUG=TRACE python train.py
  → Inspect actual all-reduce latency per link
  → If cross-network link slow: adjust topology
```

---

## Code Example

```python
import torch
from torch.profiler import profile, record_function

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
              record_shapes=True) as prof:
    with record_function("model_inference"):
        model_output = model(input_tensor)

prof.key_averages().table(sort_by="self_cuda_memory_usage", row_limit=10)
# Shows which ops use most CUDA memory

# GPU utilization check
import torch.utils.cuda as cuda
print(f"GPU 0 memory: {torch.cuda.memory_allocated(0) / 1e9:.2f} GB")

# NCCL ring topology
import os
os.environ['NCCL_DEBUG'] = 'TRACE'
dist.all_reduce(tensor)  # Check logs for ring
```

---

## Interview Checklist

- [ ] NVML vs NCCL vs nsys profilers
- [ ] Utilization vs compute vs memory-bound
- [ ] Thermal throttling detection
- [ ] NCCL ring topology and cross-network hops
- [ ] Bottleneck diagnosis (GPU idle, memory, NCCL)
- [ ] Data loading as bottleneck
- [ ] CUDA memory leaks

## Common Wrong Answers

- ❌ "High GPU utilization = good" — could still be memory-bound
- ❌ "More workers = faster data" — depends on storage (NFS bottleneck)
- ❌ "Ignore NCCL ring" — bad topology = 10x slower all-reduce
- ❌ "Thermal throttling doesn't matter" — can halve training speed
