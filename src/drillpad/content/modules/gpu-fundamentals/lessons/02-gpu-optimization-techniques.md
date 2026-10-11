# GPU Optimization: Techniques for Inference and Training

## Overview

This lesson covers:
1. Quantization (reduce memory, trade accuracy)
2. Sparsity (skip zeros, reduce compute)
3. Kernel fusion (reduce HBM traffic)
4. Tensor cores (specialized compute units)
5. Batching strategies (prefill vs decode)

---

## Quantization: Trading Precision for Speed

Most models use FP32 (32-bit floats). Inference doesn't need full precision.

```
FP32: 32 bits per value
FP16: 16 bits (training, often unstable)
INT8: 8 bits (quantized, 4x faster, 1% accuracy loss)
INT4: 4 bits (8x faster, 2-3% accuracy loss)
```

**Memory savings:**
```
Model: 7B parameters

FP32: 7B × 4 bytes = 28 GB
INT8: 7B × 1 byte = 7 GB (4x savings!)
INT4: 7B × 0.5 byte = 3.5 GB (8x savings!)

Batch size with A100 (80GB):
  FP32: batch=1 (28GB for model + batch)
  INT8: batch=8+ (7GB model + room for batch)
  INT4: batch=16+ (3.5GB model + room for batch)
```

**Types of quantization:**

1. **Post-Training Quantization (PTQ)**
   - Quantize after training (no retraining)
   - Fast, minimal accuracy loss (0.5-1%)
   - vLLM uses this
   - Simple: scale each weight to fit into INT8 range

2. **Quantization-Aware Training (QAT)**
   - Train with quantization in mind (simulate INT8 during training)
   - Better accuracy (0.1-0.5% loss)
   - Slower (requires retraining)
   - Used for demanding applications

**KV-cache quantization specifically:**
```
KV-cache grows with sequence length
7B model, batch=32, seq_len=4096

FP32 KV: 
  2 (K and V) × 32 × 4096 × (hidden_dim)
  ≈ 32GB

INT8 KV:
  Same, but 8x less
  ≈ 4GB

Huge difference! Decode is memory-bound on KV reads.
KV quantization: 4GB → 500MB
→ Enables batch=256 instead of batch=32
```

---

## Sparsity: Skipping Zeros

Many model weights are zero (pruning, or just happen to be). Sparse operations skip them.

```
Dense:       Sparse:
[1, 0, 2]    [1, 2] + indices [0, 2]
[0, 3, 0]    [3] + indices [1]
[4, 0, 0]    [4] + indices [0]

Operations: 9 weights → 4 weights (56% reduction)
```

**Two levels:**

1. **Weight sparsity** (model has ~50% zero weights)
   - Structured: entire rows/columns are zero
     - Easy for GPUs, ~2x speedup
   - Unstructured: random zeros
     - Hard for GPUs, need special formats
     - Only 1.2x speedup (overhead of indexing)

2. **Activation sparsity** (intermediate outputs have zeros)
   - Depends on data, harder to exploit
   - Some models naturally sparse (ReLU activations)
   - ~20-30% speedup typical

**Real example: Sparse Transformers**
```
Standard attention: O(n²) complexity (every token attends to every other)
Sparse attention: O(n) complexity (each token attends to local window)

Example: seq_len=4096
  Standard: 4096² = 16M attention operations
  Local (window=64): 4096 × 64 = 262K operations (60x reduction!)

Cost: Accuracy loss, specific use cases
Benefit: Massive speedup for long sequences
```

---

## Kernel Fusion: Reduce Memory Roundtrips

Without fusion:
```
y = ReLU(Linear(x))

Step 1: Linear
  Read x from HBM (1KB)
  Compute y' = W @ x + b (1M FLOPs)
  Write y' to HBM (1KB)

Step 2: ReLU
  Read y' from HBM (1KB)
  Compute y = max(0, y')
  Write y to HBM (1KB)

Total HBM traffic: 4KB
```

With fusion:
```
y = ReLU(Linear(x))

Fused kernel:
  Read x from HBM (1KB)
  Compute y' = W @ x + b
  Compute y = max(0, y') (inline, in registers)
  Write y to HBM (1KB)

Total HBM traffic: 2KB (50% reduction!)
```

**Why fusion helps:**
- Each roundtrip to HBM = ~1 microsecond
- Intermediate data stays in L1/L2 cache
- Perfect for memory-bound operations

**Common fusions:**
- Linear + ReLU (very common)
- Attention + normalization
- Embedding + positional encoding
- Multiple small matrix multiplies → one big matrix multiply

---

## Tensor Cores: Specialized Hardware

A100 has 6,912 tensor cores (not the same as regular compute cores).

```
Regular compute:  (float a, float b) → a + b
Tensor core:      (4×4 FP16 matrix A, 4×4 FP16 matrix B) 
                   → 4×4×4×4 = 256 FP32 MACs (multiply-accumulate)
```

**Speedup:**
```
Regular compute (FP32): 312 TFLOPS

Tensor cores (FP16 → FP32):
  A100 has 312 TFLOPS FP32 compute
  But tensor cores do 9.7× more efficient
  → 312 × 9.7 ≈ 3,000 TFLOPS for tensor ops!

  Inference uses FP16/TF32:
  TensorFloat32 (TF32): mix of precision, optimized for inference
  → 1,200 TFLOPS typical

Cost: Requires matrix operations, not element-wise
Benefit: 4-10x speedup for matrix multiplication
```

**Example: Inference speedup**
```
vLLM uses tensor cores for matrix multiply
  attention QK^T (matrix multiply)
  output projection (matrix multiply)

Without tensor cores: 500 TFLOPS achieved
With tensor cores: 1,200 TFLOPS achieved (2.4x speedup!)
```

---

## Batching: Prefill vs Decode

**Prefill:**
- Process N new tokens (e.g., 1024 tokens in prompt)
- Compute attention over all N tokens
- Arithmetic intensive: O(N²)
- **Should do prefill in large batches**

**Decode:**
- Process 1 token per request
- Compute attention over KV-cache of length K (e.g., 4096)
- Memory intensive: O(K)
- **Can batch many requests, limited by KV memory**

**Strategy: Continuous Batching**

```
Time 0: Queue has 32 new requests (1024 tokens each)
  Prefill batch: 32 requests, 1024 tokens each = 32K tokens
  Attention: 32K × 32K = 1B FLOPs
  GPU: 85% utilization

Time T1: First request finishes prefill, enters decode
  Prefill batch: 24 requests (8 finished)
  Decode batch: 8 requests (1 token each)
  
Time T2: More requests finish
  Prefill batch: 16 requests
  Decode batch: 16 requests
  
Result: GPU always has mix of compute-heavy (prefill) + memory-heavy (decode)
        Utilization: 60-75% throughout
```

**Token throughput:**
```
Static batching (all prefill, size=32):
  32K tokens / 100ms = 320K tokens/sec
  Then switch to decode, 32 requests × 100 tokens = 3200 tokens/sec
  Average: Much lower

Continuous batching (mixed prefill + decode):
  Prefill: 32K tokens/sec for prefill requests
  Decode: 3200 tokens/sec for decode requests
  Sustained: 200-250K tokens/sec average (better!)
```

---

## Real Optimization Path

Example: Optimize vLLM inference for 7B model, batch=128.

```
Step 1: Profile
  Measure: GPU utilization = 30% (bad)
  Identify: Memory-bound (decode phase)
  
Step 2: Quantize KV-cache
  Before: 32GB KV for batch=128, seq=4K → OOM
  After: 4GB KV → fits, enables batch=256
  Result: GPU util = 50%
  
Step 3: Fuse attention + output projection
  Before: attention writes to HBM, output reads back
  After: stay in L1 cache
  Result: GPU util = 60%
  
Step 4: Use tensor cores
  Configure: TF32 precision (mixing FP32/FP16)
  Result: GPU util = 75%
  
Step 5: Continuous batching
  Change: Don't wait for all prefill to finish
  Interleave: prefill + decode
  Result: GPU util = 80%, sustained throughput
```

---

## Most Likely Interview Questions

**Q1: "Why does quantization help inference?"**

A: "Inference is memory-bound. FP32 → INT8 reduces data 4x, so memory reads are 4x faster. Arithmetic intensity improves, GPU spends less time waiting for data. Accuracy loss is minimal (0.5-1%) because inference doesn't need gradient precision."

**Q2: "What's kernel fusion and when is it worth it?"**

A: "Fusion reduces roundtrips to HBM. If unfused kernels write intermediate (e.g., 100MB), you pay to read it back. Fused kernels keep data in cache. Worth it when total HBM traffic reduction > kernel launch overhead. Typical: 20-50% speedup."

**Q3: "How much speedup do tensor cores give?"**

A: "For matrix operations (matrix multiply in attention, projection), tensor cores are 4-10x more efficient than regular compute. For element-wise ops (ReLU, softmax), no speedup. Inference using tensor cores: 2-4x overall speedup."

**Q4: "You have 100ms to process 10k requests, each with 512-token prompt. How?"**

A: "Continuous batching with prefill + decode interleaving. Prefill is compute-heavy (1M FLOPs per request), decode is memory-bound. Batch size ~128 for GPU memory. Prefill batch processes 64K tokens/sec. Decode batch processes 30K tokens/sec. Interleave them to sustain 100K tokens/sec total. 10k×512 = 5.12M tokens / 100K tokens/sec = 51ms (fits)."

**Q5: "When would you NOT quantize?"**

A: "If accuracy loss is unacceptable (e.g., scientific computing, medical imaging). If hardware doesn't support INT8 efficiently (older GPUs). If quant overhead > speedup (rare). General rule: quantize for inference, not training (training needs gradient precision)."

---

## Key Takeaways

1. **Quantization:** 4-8x memory reduction, 0.5-3% accuracy loss, huge wins for inference
2. **Kernel fusion:** Reduce HBM roundtrips, 20-50% speedup per fusion
3. **Tensor cores:** 4-10x for matrix ops, essential for inference
4. **Batching:** Interleave compute-heavy + memory-heavy to maximize utilization
5. **Profiling first:** Identify bottleneck (compute vs memory) before optimizing
