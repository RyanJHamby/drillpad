# LoRA and Adapters: Efficient Fine-Tuning, Inference Cost

## LoRA: Low-Rank Adapters (Hu et al., 2021)

Instead of training full model weights, train small low-rank matrices.

```
Original weight: W [d, d] = 70B parameters
LoRA: W + delta_W where delta_W = A @ B
  A [d, r] (d = hidden, r = rank, usually r=8)
  B [r, d]
  Total: d*r + r*d = 2*d*r << d*d

For 70B with r=8: 70B * 8 * 2 = 1.12B extra params (1.6% overhead)
vs retraining all 70B (massive difference)

Inference: compute y = x @ (W + A @ B) = x @ W + x @ A @ B
  Extra matmuls: [batch, seq, d] @ [d, r] @ [r, d] (cheap, r small)
  Overhead: ~2–5% latency
```

---

## Inference Cost

```
Base model: 70B parameters, 50 ms per token
With LoRA (r=8): 50 + 2 = 52 ms per token (4% slower)
Memory: same 35 GB (LoRA params fit in cache)

vs retraining full model:
  170B parameters on same 8-GPU setup → 2.4x slower
  or need 16 GPUs (higher cost)

LoRA: cheapest way to adapt models for many tasks.
```

---

## Multiple LoRAs: Inference Scheduling

Deploy model + 100 different LoRAs (one per customer task).

```
Request arrives: customer_id=37, wants specialized behavior
  Load base model (35 GB, shared)
  Load LoRA_37 (0.56 MB, customer-specific)
  Run inference with both
  
Warm-up cache with LoRA: ~1 ms
Switching between customers: reload LoRA (same base model)
```

Enables personalization at scale.

