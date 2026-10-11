# Tensor Parallelism: Weight Sharding and GEMM Decomposition

## The Problem: Single GPU Fits 7B, Not 70B

```
Model size: 70B parameters = 70B * 2 bytes (fp16) = 140 GB
GPU memory: H100 = 80 GB (can't fit)

Options:
  1. Quantization (4-bit) → 70B * 0.5 bytes = 35 GB (fits, but accuracy loss)
  2. Offload to CPU (slow, defeats purpose)
  3. Shard across multiple GPUs (tensor parallelism)
```

Tensor parallelism splits weights across GPUs.

---

## Matrix Multiplication: Row vs Column Sharding

For a linear layer: `y = x @ W + b` where x is [batch, in_dim], W is [in_dim, out_dim].

```
Standard (single GPU):
  x: [32, 4096]
  W: [4096, 4096]
  y = x @ W = [32, 4096]

Tensor parallelism (2 GPUs):
  Split W by columns:
  GPU 0: W_0 = [4096, 2048]  (first 2048 output dims)
  GPU 1: W_1 = [4096, 2048]  (last 2048 output dims)
  
  x @ W_0 = [32, 2048] (on GPU 0)
  x @ W_1 = [32, 2048] (on GPU 1)
  
  Concatenate: y = [x @ W_0 | x @ W_1] = [32, 4096]
  
  Communication: AllGather to gather x on both GPUs, or broadcast x (2 rounds)
```

**Key insight:** Each GPU computes its own part of the output, no synchronization during matmul (parallelizable).

---

## Attention with Tensor Parallelism

Attention is: `out = softmax(Q @ K^T / sqrt(d)) @ V`

```
Single GPU:
  Q, K, V: [batch, seq, hidden]
  Q @ K^T: [batch, seq, seq]  (compute attention scores)
  softmax → [batch, seq, seq]
  attention @ V: [batch, seq, hidden]

Tensor parallelism (split by head):
  8 heads, each head_dim = 64 (hidden = 512)
  
  GPU 0: heads 0–3
  GPU 1: heads 4–7
  
  Each GPU computes attention for its heads independently.
  No communication during the softmax/matmul (softmax is per-sequence, not cross-GPU).
  
  After attention: AllGather to collect all heads, or Reduce if outputting separately.
```

**Attention is expensive:** softmax must be computed on full seq_len. If you shard sequence length across GPUs, you'd need AllReduce on the numerator/denominator (expensive). Better to shard by head or by batch.

---

## All-Reduce Bottleneck

After each layer, you might need to aggregate results.

```
Example: decoder layer with tensor parallelism

Forward:
  1. Linear layer (sharded by output dim): y_0 = x @ W_0, y_1 = x @ W_1 (on GPU 0, GPU 1)
  2. Activation: ReLU(y_0), ReLU(y_1)
  3. AllGather(y): combine y_0, y_1 → [batch, hidden] on both GPUs
  4. Attention: each GPU has full hidden dim, computes attention for its heads
  5. AllGather: combine attention outputs
  6. Linear layer 2: output sharded again
```

Each AllGather costs bandwidth: moving output across network.

For a 70B model with 80 layers:
```
Per layer AllGather: [batch, seq, hidden] = [32, 4096, 4096] fp16 = 1 GB
80 layers * 1 GB = 80 GB moved per forward pass
At 600 GB/s InfiniBand (A100 NVLink): 80 GB / 600 GB/s = 133 ms per forward pass

Compute time (rough): 70B FLOPs / 312 TFLOPS (A100) ≈ 225 ms
Communication time: 133 ms
Total: 358 ms per forward pass (communication is 37% of time)
```

**Balanced design:** communication should be << computation. If communication dominates, you're communication-bound, not compute-bound.

---

## Practical Strategies

**Strategy 1: Overlap compute and communication**
```
While GPU 0 computes layer N, start AllGather for layer N-1 output (from previous step).
Requires: pipeline (different mini-batches on different layers simultaneously).
```

**Strategy 2: Reduce communication frequency**
```
Instead of AllGather after every layer, accumulate 2–4 layers before gathering.
Trade-off: increased memory (store intermediate activations), but fewer AllGathers.
```

**Strategy 3: Mixed precision**
```
AllGather uses fp16 (half the bandwidth of fp32).
Reduce data by 2x → 37% → 18.5% communication overhead (better).
```

---

## Q&A

**Recall 1:** How does tensor parallelism split a linear layer across GPUs? What communication is needed?

*Answer:* Split weight matrix by output dimension (columns). Each GPU computes its portion of the output independently. Then AllGather (or broadcast) to combine outputs on all GPUs. Communication cost is proportional to output size.

**Probe 1:** You have 4 GPUs, 70B model. Tensor parallelism (TP=4) splits weights by 4. How much memory per GPU?

*Expected:* 70B / 4 = 17.5B parameters per GPU. 17.5B * 2 bytes (fp16) = 35 GB per GPU (fits on H100 80GB with activation/cache).

**Numeric 1:** AllGather [batch=32, seq=4096, hidden=4096] fp16 on 4 GPUs. Bandwidth 900 GB/s (NVLink). Latency?

*Working:* 32 * 4096 * 4096 * 2 bytes = 1 GB. 1 GB / 900 GB/s ≈ 1.1 ms.

**Story:** vLLM's tensor parallelism (2023) exposed a bug: AllGather was happening after every layer, but some layers could batch the AllGather with computation. Fixing the schedule dropped latency by 15%.

