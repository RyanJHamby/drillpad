# FlashAttention & GPU Kernels: I/O Efficiency and Memory Optimization

## The Problem: Attention is I/O-Bound, Not Compute-Bound

Standard attention (PyTorch, CUDA) reads the full KV cache into GPU memory for every token.

```
Standard attention (e.g., in vLLM without kernel fusion):

Forward pass for one query token:
  1. Read Q from registers: [1, head_dim] (tiny, ~256 B)
  2. Read K from HBM (GPU VRAM): [seq_len, head_dim] (4096 * 64 * 2 = 512 KB)
  3. Read V from HBM: [seq_len, head_dim] (512 KB)
  Total: 1 MB per attention layer per token
  
  At 80 GB/s GPU memory bandwidth (H100): 1 MB = 12.5 µs just to read
  Compute (Q @ K^T): [1, 4096] @ [4096, 64] = 4K multiplications = ~10 µs
  Result: memory read (12.5 µs) >> compute (10 µs) — MEMORY BOUND.

Batch size 128:
  128 tokens * 1 MB = 128 MB read per layer
  128 layers * 128 MB = 16.4 GB per forward pass
  H100 has 3.3 TB/s memory bandwidth, but also other layers competing.
  Result: GPU utilization ~20% (stalled waiting for memory).
```

**Measured (Nvidia H100):**
- Standard attention: 10% peak FLOP utilization
- FlashAttention: 50%+ peak FLOP utilization (5x improvement)

---

## FlashAttention: I/O-Aware Algorithm

**Key idea:** Compute attention in a way that minimizes **HBM (high bandwidth memory) accesses**.

Instead of:
1. Load full K, V → HBM to on-chip memory (SRAM)
2. Compute all attention scores
3. Softmax
4. Write intermediate results back to HBM

Do:
1. Load a **tile** (block) of K, V, Q
2. Compute attention for that tile **without writing intermediate results back**
3. Use SRAM as a scratchpad (much faster than HBM)
4. Finalize softmax at the end

```
Memory hierarchy and bandwidth:

GPU Memory Levels:
┌─────────────────────────────────────────────┐
│ Registers (per thread):                     │
│ - 255 KB per thread (can hold small tensors)│
│ - ~10 TB/s bandwidth (within thread)        │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ Shared Memory (per SM, ~96 KB):             │
│ - 96 KB shared across ~128 threads          │
│ - ~1.9 TB/s bandwidth (on-chip)             │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ L2 Cache (192 MB shared):                   │
│ - 6.6 TB/s bandwidth (partially on-chip)    │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ HBM (80 GB, 3.3 TB/s):                      │
│ - Main memory, slow                         │
└─────────────────────────────────────────────┘

FlashAttention reduces HBM reads by computing locally in shared memory.
```

---

## FlashAttention Algorithm (Simplified)

```
Input:
  Q: [seq_len, head_dim] (all query positions, but we'll tile)
  K, V: [seq_len, head_dim]
  Block size: Br (row) and Bc (col), typically 64–256

Algorithm:
  For i in range(0, seq_len, Br):
    Load Q_i from HBM into SRAM: [Br, head_dim]
    
    For j in range(0, i+1, Bc):  (causal: only attend to past)
      Load K_j from HBM: [Bc, head_dim]
      Load V_j from HBM: [Bc, head_dim]
      
      S_ij = Q_i @ K_j^T  (compute in SRAM)
      P_ij = softmax(S_ij)  (compute in SRAM, not written to HBM!)
      O_i += P_ij @ V_j  (accumulate output in SRAM)
    
    Write O_i back to HBM (only output, not intermediate)

Key: Intermediate matrices (S_ij, P_ij) stay in SRAM.
Benefit: Fewer HBM reads/writes.
```

**IO complexity analysis:**

Standard attention:
```
Q: read from HBM (Θ(seq_len * head_dim) reads)
K: read from HBM (Θ(seq_len * head_dim) reads)
V: read from HBM (Θ(seq_len * head_dim) reads)
Intermediate S: write to HBM (Θ(seq_len^2) reads/writes — EXPENSIVE!)
Intermediate P: write to HBM (Θ(seq_len^2))
Total: Θ(seq_len^2) HBM traffic

FlashAttention (with tiling):
Q: read once from HBM
K, V: read (seq_len / block_size) times (reused across blocks)
S, P: computed and discarded in SRAM (not written)
Total: Θ(seq_len) HBM traffic (for Q, K, V) + constant overhead
```

**Measured reduction (Tri Dao et al., 2022):**
- Standard: 100 HBM bytes read per attention step
- FlashAttention: 15 HBM bytes read per attention step
- 6.7x fewer HBM reads

---

## Story: vLLM's Kernel Bottleneck

**Setup:** vLLM with PagedAttention (2023). Decode throughput plateaued at 52 req/s on H100.

**Initial profiling:**
```
perf report shows:
  - 60% time in attention kernel
  - 70% GPU memory stall time
  - HBM bandwidth at 2.2 TB/s (out of 3.3 TB/s available)
  - GPU compute utilization: 15%
```

**Root cause:** vLLM was using standard attention, not FlashAttention.

**Fix:** Replace with FlashAttention-2 kernel (CUDA, hand-optimized).

**Result:**
```
After fix:
  - 20% time in attention kernel (3x faster per operation)
  - Attention now limited by compute, not memory
  - Throughput: 52 → 150 req/s (2.9x overall)
  - GPU compute utilization: 45%
```

**Key insight:** Algorithmic improvements (I/O-aware) beat raw GPU parallelism.

---

## When to Use FlashAttention

| Scenario | Use FlashAttention? | Why |
|----------|-------|-----|
| Inference (decode, single token) | YES | Memory-bound; 6–10x speedup |
| Inference (prefill, batched) | YES | Memory-bound for large batches |
| Training (forward/backward) | YES | Saves memory for backprop (doesn't materialize S, P) |
| Very short sequence (< 64 tokens) | MAYBE | Overhead of tiling might exceed benefits |
| Attention with custom masking (sparse) | NO | FlashAttention assumes dense, sequential masking |
| Very small batch (1–2 requests) | MAYBE | GPU parallelism unused; compute bound |
| Serving with fused operators | YES | Reduces memory bottleneck, keeps GPU busy |

---

## Q&A (Real Interview Depth)

**Recall 1:** Why is standard attention memory-bound, not compute-bound?

*Must-say:*
- Standard: Load Q, K, V from HBM, compute S = Q @ K^T (O(n²) for seq_len n).
- Compute: ~n² multiplications.
- Memory: Read K, V = 2n * head_dim floats = O(n) memory.
- Compute/memory ratio: O(n²) / O(n) = O(n).
- For large n, memory moves dominate. For n = 4096, this is 4096x operations per byte.
- But GPU compute is ~100 TFLOPS and memory is ~3 TB/s = 0.003 TFLOPS/GB.
- Memory bound means memory latency >> compute time.

*Interview-style context:* "Your latency budget for a token is 100 ms. Attention reads 1 GB of KV from HBM in 300 µs. Compute takes 1 ms. Which dominates?"

**Probe 1:** FlashAttention keeps intermediate matrices (S, P) in SRAM. SRAM is 96 KB per SM. For seq_len 4096, head_dim 64, S matrix is 4096 * 4096 * 2 bytes = 32 MB. How does it fit?

*Expected:*
- It doesn't fit all at once.
- FlashAttention uses **tiling**: process 64–256 tokens at a time (block size).
- Per block: S is [Br, Bc] = [256, 256] * 2 bytes = 128 KB.
- 96 KB shared memory < 128 KB, but 96 KB is per SM and multiple SMs run in parallel.
- Also, S is reused within the tile before being discarded.

*Answer:* "By tiling. We don't fit the full S matrix; we compute and discard tile-by-tile."

**Numeric 1:** Standard attention reads K, V from HBM for each query position. Decode batch size 64, seq_len 4096, head_dim 64. Total HBM reads?

*Working:*
- K: 4096 * 64 * 2 bytes = 512 KB
- V: 512 KB
- Per token in batch: 1 MB
- Batch of 64: 64 MB
- If you do this for 64 decode steps (generating 64 tokens): 64 * 64 MB = 4 GB
- H100 3.3 TB/s: 4 GB / 3.3 TB/s = 1.2 ms just for memory

**Numeric 2:** FlashAttention with block size 256. Seq_len 4096. How many blocks of K loaded from HBM?

*Working:* 4096 / 256 = 16 blocks. Each block reused for all query positions. 16 * 256 * 64 * 2 = 512 KB (same total, but tiled to fit in cache).

**Story:** Nvidia's FlashAttention (2022) revolutionized inference because it showed that **algorithmic optimization beats throwing more GPU cores at the problem**. Many teams were trying to parallelize attention further; Tri Dao showed the bottleneck was I/O, not parallelism. vLLM adopted it and saw 3x throughput gains.

---

## Checklist & Common Pitfalls

- [ ] **Measure attention latency before and after.** Many engineers claim FlashAttention "just works"; it does, but verify the speedup on your workload.
- [ ] **Check that intermediate matrices (S, P) are not written to HBM.** If they are, you're not getting the benefit.
- [ ] **Ensure block size is tuned for your GPU.** H100 and A100 have different SRAM sizes.
- [ ] **Verify numeric stability.** FlashAttention uses a different softmax numerics (online softmax). Should match, but test with small inputs.
- [ ] **Understand when you'll be compute-bound vs memory-bound after.** After FlashAttention, attention might become compute-bound. Next bottleneck is elsewhere.

**Common wrong answer:** "FlashAttention is always faster." 
*Corrected:* "FlashAttention is faster when attention is memory-bound. If you have a very small batch or sequence, it might not help."

---

## References & Next Steps

- Read vLLM's PagedAttention + FlashAttention-2 integration (2023).
- Implement a minimal FlashAttention in CUDA to understand the tiling.
- Profile your inference service: is attention the bottleneck?
