# Pipeline Parallelism: Bubbles & 3D Parallelism

## 3D Parallelism

```
Model parallelism: split layers across GPUs
  Layer 1-10 → GPU0, Layer 11-20 → GPU1, ...
  Sequential: GPU0 processes, sends to GPU1, waits
  
Pipeline parallelism: keep all GPUs busy
  Micro-batches: batch 128 → 16 micro-batches of 8
  
  Timeline (4 GPUs):
  
  MB1: [GPU0 ████] [GPU1 ████] [GPU2 ████] [GPU3 ████]
  MB2:    [GPU0 ████] [GPU1 ████] [GPU2 ████] [GPU3 ████]
  MB3:       [GPU0 ████] [GPU1 ████] [GPU2 ████] [GPU3 ████]
  MB4:          [GPU0 ████] [GPU1 ████] [GPU2 ████] [GPU3 ████]
  
  Overlap: while GPU3 processes MB1, GPU0 processes MB2
  Result: all GPUs busy (utilization ↑)

Data parallelism: replicate model, split data
  Same model on 4 GPUs, each gets batch_size/4
  Communicate: all-reduce gradients per step
  
3D = data + pipeline + tensor parallelism:
  ├─ Data: replicate model, different batch
  ├─ Pipeline: micro-batch parallelism
  ├─ Tensor: split weights within layer
  └─ Combined: 16x32x32 = 16K GPUs viable (larger models)
```

## Pipeline Bubbles

```
Forward pass (F): compute activations
Backward pass (B): compute gradients
Update (U): apply optimizer

Single GPU schedule:
  F1 → B1 → U1 → F2 → B2 → U2

Pipeline (4 GPUs, 2 micro-batches):
  GPU0: F1 F2 B1 B2 U
  GPU1:    F1 F2 B1 B2
  GPU2:       F1 F2 B1 B2
  GPU3:          F1 F2 B1 B2
  
  Bubble: GPU0 waits for GPU3 (no work during U phase)
  Efficiency: (F+B) / (F+B+U) ≈ 0.8 (good)

More bubbles with fewer micro-batches:
  GPU0: F B U
  GPU1:   F B U
  GPU2:     F B U
  GPU3:       F B U
  
  Bubble: huge! (U phase, only one GPU working)
  Efficiency: 0.25 (bad)

Solutions:
  ├─ More micro-batches (more work to hide bubble)
  ├─ Gradient accumulation (batch logical_batch_size)
  ├─ Interleaved scheduling (more complex)
  └─ Trade-off: more memory for more micro-batches
```

## Synchronization Cost

```
All-reduce (sync gradients across GPUs):

Ring all-reduce (N GPUs):
  Steps: 2(N-1)
  Example (4 GPUs): 2*3 = 6 steps
  Latency: 6 * RTT + time to send gradient size
  
  Latency = 6 * 1ms + (gradient_size / bandwidth)
  
  Example:
    ├─ Gradient size: 1 GB (large model)
    ├─ Bandwidth: 1 Gbps = 125 MB/s
    ├─ Time: 1 GB / 125 MB/s = 8 sec
    ├─ Total: 6ms + 8s = 8.006 sec
    └─ Compute time: 5 sec (gradient computation)
    
  Efficiency: 5 / (5 + 8) = 38% (bad!)

Solution: reduce gradient size
  ├─ Gradient compression: drop small gradients
  ├─ Quantization: fp32 → int8 (4x reduction)
  ├─ New time: 1 sec all-reduce
  └─ Efficiency: 5 / (5 + 1) = 83% (good!)
```

---

## Interview Checklist

- [ ] 3D parallelism: data + pipeline + tensor
- [ ] Pipeline bubbles and micro-batch sizing
- [ ] Efficiency = compute / (compute + bubble)
- [ ] All-reduce synchronization cost
- [ ] Gradient compression + quantization
- [ ] Schedule: GPUs don't idle

## Common Wrong Answers

- ❌ "Ignore pipeline bubbles" — can cut utilization 50%
- ❌ "Maximize micro-batches" — memory explodes
- ❌ "Skip all-reduce compression" — synchronization dominates
