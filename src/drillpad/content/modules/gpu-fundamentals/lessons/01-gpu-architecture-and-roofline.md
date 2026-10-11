# GPU Architecture: Compute, Memory, and the Roofline Model

## Overview

This lesson covers:
1. GPU architecture (SMs, warps, threads)
2. Memory hierarchy (L1, L2, HBM, bandwidth)
3. Roofline model (compute-bound vs memory-bound)
4. When to use GPU (and when not to)
5. Optimization strategies per bottleneck

---

## GPU vs CPU: Different Design

**CPU:** Few cores (8-16), high clock speed (3-5 GHz), big caches, out-of-order execution
- Optimized for **latency** (minimize time to first result)
- Good at complex control flow

**GPU:** Thousands of small cores (10,000+), lower clock (1-2 GHz), small caches, in-order
- Optimized for **throughput** (maximize work done per second)
- Requires massive parallelism (1000+ threads in flight)

```
CPU: 16 cores, each ultra-powerful
┌─────────────────────────────────┐
│ [Core1 with big cache]          │
│ [Core2 with big cache]          │
│ ... × 16                        │
└─────────────────────────────────┘

GPU: 10,880 cores (A100), each simple
┌──────────────────────────────────────┐
│ [SM0] [SM1] [SM2] ... [SM79]        │  (80 SMs)
│  ↓     ↓     ↓        ↓            │
│ [32 cores] [32 cores] ... [32 cores] │ (32 cores per SM)
│ (called "lanes")                   │
└──────────────────────────────────────┘
```

---

## GPU Memory Hierarchy

**A100 (80 GB variant):**

```
Level       Size    Bandwidth   Latency   Who can access
───────────────────────────────────────────────────────
L1          20KB    ~12 TB/s    1 cycle   Same warp only
L2          40MB    ~3.7 TB/s   ~20 cycles All threads
HBM         80GB    2.0 TB/s    ~200 cycles All threads
```

**Bandwidth arithmetic:**
- Peak FLOPS (A100): 312 TFLOPS (FP32)
- Peak bandwidth: 2.0 TB/s = 2 × 10^12 bytes/sec
- Arithmetic intensity: FLOPS / (bytes read) = 312×10^12 / (2×10^12) = 156 FLOPS per byte

**In practice:** Matrix multiply (FP32, typical workload) needs ~0.5 FLOPS per byte of data (heavy data movement). So A100 is memory-bound for most inference.

---

## The Roofline Model

Roofline plots maximum throughput given arithmetic intensity:

```
log(Throughput)
│     ╱╱╱╱╱╱╱ Compute ceiling (312 TFLOPS)
│    ╱╱╱╱╱╱
│   ╱╱╱╱╱╱   (steep: compute-bound here)
│  ╱╱╱╱╱╱
│ ╱╱╱╱╱╱
├─────────────┼─────────────────── (2.0 TB/s × arithmetic intensity)
│             │ Memory bandwidth ceiling
│             │ (gentle slope: memory-bound here)
│             │
└─────────────┼──────────────────────→ log(Arithmetic Intensity)
              ridge point
```

**Ridge point:** Where compute and memory ceilings meet.

```
Ridge = Compute ceiling / Bandwidth ceiling
      = 312 TFLOPS / 2.0 TB/s
      = 156 FLOPS per byte
      
If workload has < 156 FLOPS/byte → memory-bound
If workload has > 156 FLOPS/byte → compute-bound
```

---

## Example: Matrix Multiply (C = A × B, all 1024×1024 matrices)

```
A: 1024×1024 = 1M elements = 4MB (FP32)
B: 1024×1024 = 1M elements = 4MB
C: 1024×1024 = 1M elements = 4MB (output)

Computation: C[i,j] = sum over k: A[i,k] * B[k,j]
             = 1024 multiplications per output element
             = 1024^3 = 1B FLOPs total

Data movement:
  - Load A: 4 MB
  - Load B: 4 MB
  - Store C: 4 MB
  - Total: 12 MB

Arithmetic intensity: 1B FLOPs / 12 MB = 1B / (12×10^6) ≈ 83 FLOPS/byte

Is 83 > 156 (ridge)? No → MEMORY-BOUND

Predicted throughput:
  Bandwidth ceiling: 2.0 TB/s × 83 FLOPS/byte = 166 TFLOPS
  Actual A100: achieves ~150 TFLOPS (close!)
```

---

## Optimization Strategies

### If Compute-Bound (> 156 FLOPS/byte)

**Example:** Complex image processing (80+ FLOPs per pixel read)

**Strategies:**
1. **Increase thread count:** More warps in flight hides latency
2. **Reduce register pressure:** Less per-thread state allows more threads
3. **Fuse kernels:** Avoid reading/writing intermediate tensors to HBM
4. **SIMD operations:** Use tensor cores (if available, get 10x speedup)

```
Naive: 
  kernel_1(A → B)    [reads A from HBM, writes B to HBM]
  kernel_2(B → C)    [reads B from HBM, writes C to HBM]
  
Fused:
  kernel_fused(A → C)  [reads A once, computes B in registers, writes C]
  Result: 2x reduction in HBM bandwidth usage
```

### If Memory-Bound (< 156 FLOPS/byte)

**Example:** Inference (matrix-vector multiply, low arithmetic intensity)

**Strategies:**
1. **Increase batch size:** Amortize memory cost across more outputs
2. **Quantization:** 4-bit instead of 32-bit = 8x less bandwidth
3. **Sparsity:** Skip zero elements
4. **Increase arithmetic intensity:** Matrix multiply instead of vector

```
Memory-bound: 1000×1024 × 1024×1 = 1M FLOPs, 4MB data, 0.25 FLOPS/byte
  Throughput: 2.0 TB/s × 0.25 = 500 GB/s (only 0.5% of GPU used!)

Batch it: 1000×1024 × 1024×64 = 64M FLOPs, 256MB data, 0.25 FLOPS/byte
  Still memory-bound, but now using batch operations (better kernel efficiency)

Quantize: 4-bit reduces data to 1MB (×4 reduction)
  1M FLOPs, 1MB data, 1.0 FLOPS/byte
  Still memory-bound, but faster
```

---

## When to Use GPU?

**Use GPU if:**
- Arithmetic intensity > 10 FLOPS/byte (memory-bound is fine, still beats CPU)
- Massive parallelism (100k+ threads worth of work)
- Latency-tolerant (can hide 200-cycle memory access with other work)

**Use CPU if:**
- Low parallelism (<100 threads of work)
- Complex control flow (if/else branches)
- Latency-critical, small workload
- Memory-bound inference (quantize to 4-bit, then GPU beats CPU 10-100x)

---

## Real Example: LLM Inference

```
Model: 7B parameters, batch=32

Prefill phase (generate first token):
  Input: 32 sequences × 1024 tokens = 32K tokens
  Attention: 32K×32K = 1B FLOPs (quadratic)
  Data: 32K tokens × 2 bytes (quantized) = 64KB
  Arithmetic intensity: 1B / 64KB ≈ 16K FLOPS/byte
  → COMPUTE-BOUND (16K >> 156)
  → GPU utilization: ~85%

Decode phase (generate next token):
  Input: batch=32, 1 token per request
  Attention: 32 × 1 × 1024 = 32K FLOPs (linear)
  Data: 32K × 2 = 64KB
  Arithmetic intensity: 32K / 64KB = 0.5 FLOPS/byte
  → MEMORY-BOUND (0.5 << 156)
  → GPU utilization: ~1% (terrible!)

Solution: Interleave prefill + decode
  Batch has 16 prefill requests (compute-heavy) + 16 decode (memory-heavy)
  Memory serves decode while compute serves prefill
  GPU utilization: ~75% (much better)
```

---

## Most Likely Interview Questions

**Q1: "Why is inference memory-bound?"**

A: "Inference (decode) processes one token at a time. Attention is O(n) in sequence length, not O(n²). With batch=32, you read 32KB of KV-cache, do ~32K FLOPs. Arithmetic intensity = 32K / 32KB = 1 FLOP/byte. Ridge point is 156. So you're 150x below peak memory bandwidth saturation. GPU spends 99% waiting for data, 1% computing."

**Q2: "How do you make inference faster?"**

A: "Three approaches: (1) Quantization: 4-bit reduces memory 8x, makes GPU spend less time waiting. (2) Batch larger: process 128 tokens in batch, higher intensity. (3) Continuous batching: interleave prefill (compute-heavy) with decode (memory-heavy) so GPU always has work."

**Q3: "What's arithmetic intensity and why does it matter?"**

A: "FLOPS per byte of data read. If you do 1 FLOP per byte, your throughput is limited by memory bandwidth (2 TB/s → 2 TFLOPS). If you do 200 FLOPs per byte, you hit compute ceiling (312 TFLOPS). Roofline model shows the maximum possible throughput given your arithmetic intensity."

**Q4: "You want to fuse two kernels. What's the benefit?"**

A: "Reduces HBM traffic. Instead of writing intermediate results to HBM and reading them back, you keep them in registers/L1. If intermediate is 100MB, you save 200MB of bandwidth (write + read). At 2 TB/s, that's 100 microseconds saved."

**Q5: "How do you measure if your kernel is compute or memory-bound?"**

A: "Use profiler: (1) Measure FLOPS achieved, (2) Measure GB/s of data read, (3) Calculate achieved FLOPS/byte, (4) Compare to ridge point (156 for A100). Also: utilization metrics. Compute-bound kernels have high SM utilization. Memory-bound kernels have low SM utilization, high memory bus utilization."

---

## Key Takeaways

1. **GPU has 1000x more threads, 10x less cache, 2x lower clock**
2. **Roofline model predicts max throughput** (combine compute + memory ceilings)
3. **Prefill is compute-bound, decode is memory-bound**
4. **Quantization helps memory-bound workloads** (8x less data)
5. **Batch size matters** (amortize latency, increase intensity)
