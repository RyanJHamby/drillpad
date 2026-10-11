# MQA/GQA/MLA and KV-Cache Size

## Attention Mechanism

```
Standard multi-head attention:
  Query (Q): bsz, seq_len, d_model
  Key (K): bsz, seq_len, d_model
  Value (V): bsz, seq_len, d_model
  
  Separate per head:
    Q_h: bsz, num_heads, seq_len, head_dim
    K_h: bsz, num_heads, seq_len, head_dim  ← store in cache
    V_h: bsz, num_heads, seq_len, head_dim  ← store in cache
  
  Attention(h) = softmax(Q_h @ K_h.T / √d) @ V_h
  
  KV cache size per token:
    2 * bsz * num_heads * head_dim * bytes_per_value
    = 2 * bsz * 32 * 128 * 2 (fp16)  [assuming 32 heads, 128 dim]
    = 16 KB per token
    
  For 100 tokens:
    100 * 16 KB = 1.6 MB (per request, grows with context length)
```

## Multi-Query Attention (MQA)

```
All heads share same Key/Value (only 1 copy):
  
  Q: bsz, num_heads, seq_len, head_dim
  K: bsz, 1, seq_len, head_dim  ← only 1, not num_heads
  V: bsz, 1, seq_len, head_dim  ← only 1
  
  Attention(h) = softmax(Q_h @ K.T) @ V
    └─ Each head uses same K, V (broadcast)
  
  KV cache size:
    2 * bsz * 1 * head_dim * bytes
    = 2 * bsz * 128 * 2 (fp16)
    = 256 bytes per token
    
  100 tokens: 25 KB (64x reduction from standard!)
  
  Trade-off:
    ✓ Smaller cache, more batch size
    ✗ Slightly lower quality (heads share attention)
    
  Models: PaLM, Falcon use MQA
```

## Grouped-Query Attention (GQA)

```
Middle ground: num_kv_heads < num_query_heads
  
  Q: bsz, num_heads=32, seq_len, head_dim
  K: bsz, num_kv_heads=8, seq_len, head_dim
  V: bsz, num_kv_heads=8, seq_len, head_dim
  
  Grouping: 4 query heads → 1 KV head
    Heads 0-3: use KV[0]
    Heads 4-7: use KV[1]
    ...
  
  Cache size:
    2 * bsz * 8 * 128 * 2 = 4 KB per token
    
  Ratio: standard 16KB → GQA 4KB = 4x reduction
  
  Trade-off:
    ✓ Much smaller than standard
    ✓ Better quality than MQA
    ✗ More complex to implement
    
  Models: Llama 2, GPT-4 use GQA
```

## KV-Cache Math

```
Model: Llama 70B with 80 heads, GQA (num_kv_heads=10)

Per token memory:
  2 (K and V) * bsz * 10 * 8192/80 * 2 bytes (fp16)
  = 2 * bsz * 10 * 102.4 * 2
  ≈ 4 KB per token

For seq_len=4096 (full context):
  4 KB * 4096 = 16 MB per request

Batch size capacity (80GB GPU):
  80 GB / 16 MB = 5000 requests (parallel)
  OR: 1 request, 4096 tokens, repeated 5000 times

Inference speed:
  ├─ Memory bandwidth: 2TB/s (A100)
  ├─ Token throughput: 2TB/s / 4KB = 500K tokens/sec
  ├─ At 100 tokens/request: 5K req/sec
  └─ Reasonable for single A100

Prefill vs Decode:
  ├─ Prefill (new request): Q,K,V all computed (slow)
  ├─ Decode (next token): only new K,V computed (fast, mem-bound)
  └─ KV cache: key difference
```

---

## Interview Checklist

- [ ] Standard attention: 16KB per token per request
- [ ] MQA: 256 bytes (64x reduction)
- [ ] GQA: 4KB (4x reduction, better quality)
- [ ] KV-cache grows with context length
- [ ] Batch capacity limited by KV cache size

## Common Wrong Answers

- ❌ "KV-cache size doesn't matter" — limits batch size
- ❌ "MQA == GQA" — MQA is extreme, GQA is balanced
- ❌ "Ignore KV-cache in prefill" — prefill is compute-bound, still matters
