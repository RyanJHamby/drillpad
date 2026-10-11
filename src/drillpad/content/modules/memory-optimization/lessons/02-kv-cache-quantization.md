# KV-Cache Quantization: Per-Token Scaling, Grouped Quantization

## Challenge: Activation Range Varies Per Token

Unlike weights (static), KV activations change per request, per token. Can't calibrate offline.

```
Token 0: K matrix range [−2, 3]
Token 1: K matrix range [−8, 8]
Token 100: K matrix range [−0.5, 0.5]

Per-token scaling: each token's K/V gets its own scale/zero-point.
Metadata: 1 scale + 1 zero-point per token per batch = 2 values * seq_len * batch = 1 MB (acceptable).

Quantize K for token 0: scale = 3/127, then int8 = round((K - 0) / scale)
Quantize K for token 1: scale = 8/127, then int8 = round((K - 0) / scale)
```

---

## Grouped Quantization (kv-quant in vLLM)

Split K/V by groups (e.g., 8 groups per token) instead of per-token. Reduces metadata.

```
K shape: [seq_len=4096, hidden=4096]
Groups: 4096 / 8 = 512 groups per token
Scales: 512 per token * 4096 tokens = 2M scales (too much)

Better: 8 values per group, fixed groups across all tokens.
Scales: 8 per token = 32 KB for 4K seq (fits in L2 cache).
```

---

## Attention Matmul with Quantized KV

```
Q_fp16 @ K_int8^T requires dequantization within kernel.

Kernel:
  for each query position:
    for each key position:
      k_int8 = load quantized K
      k_scale = load scale for this k_position
      k_fp16 = k_int8 * k_scale + zero_point
      score = q_fp16 @ k_fp16
      
Dequant cost: ~10 ns per element (overhead ~5% of attention kernel time).
Memory savings: 8 GB KV → 1 GB KV (at batch 32, seq 4K). Major win.
```

---

## Streaming KV: Per-Token Append

New tokens generate new K/V. With quantization, quantize on arrival.

```
Request arrives: compute K_0, V_0
  Quantize (K_0, scale_0) → int8_K_0
  
Next token: compute K_1, V_1
  Quantize (K_1, scale_1) → int8_K_1
  
Append int8_K_1 to cache (no recomputation, scales are already computed).

Amortized: ~10 μs to quantize one token's K/V (negligible).
```

---

## Accuracy: KV Quantization Impact

Perplexity increase: ~1–3% (less impact than weight quantization, because attention scores are somewhat robust to noise).

Some approaches: keep K in FP16, quantize only V (saves half the cache, ~1% perplexity impact).

