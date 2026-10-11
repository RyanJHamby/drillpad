# Mixture-of-Experts (MoE) & Expert Parallelism: Load Balancing, Routing, and Scaling

## The Problem: Dense Models Hit Memory and Compute Walls

A 70B dense LLM requires dense forward pass through all 70B parameters. This limits throughput and memory efficiency.

```
Dense model (70B, 80 layers, 4096 hidden):

Per-layer FLOP cost:
  Attention: ~2 * seq_len * hidden^2 * layers ≈ constant per seq length
  FFN (feed-forward network): hidden * hidden * 4 * 2 = 4096 * 4096 * 4 * 2 ≈ 134 million FLOPs per layer
  Total FFN for 80 layers: ~10 billion FLOPs

Memory per layer:
  Weights: (4096 * 4096) * 4 (intermediate) * 2 layers (gate, up) = ~128 MB per layer
  All layers: 128 * 80 = 10.2 GB just for FFN weights

Bottleneck:
  - All parameters must fit in memory (or be offloaded, slow)
  - All parameters contribute to latency (longer forward pass)
  - Can't specialize: one model tries to do reasoning, memorization, coding, etc. equally
```

**Real measurement (Llama 70B on 2x H100):**
```
Inference throughput: ~20–30 tokens/sec (single batch)
Why slow? FFN parameters dominate latency; compute is not fully utilized.
```

---

## Mixture-of-Experts: Selective Activation

**Key idea:** Instead of a dense FFN, use many small **experts** and a **router** that selects which experts to use per token.

```
Dense FFN (traditional):
  Input: [batch, seq, hidden] = [32, 4096, 4096]
  FFN layer: hidden → hidden*4 → hidden
    Intermediate: [32, 4096, 16384] (all activated)
    Output: [32, 4096, 4096]

Mixture-of-Experts (MoE):
  Input: [batch, seq, hidden] = [32, 4096, 4096]
  Router: logits over N experts (N = 8, 16, 32, 128...)
  Per token: select top-k experts (k = 2)
  Activated: [32, 4096, 4096] → router → [32, 4096, 2] (indices of top-2 experts)
  
  For each token, compute FFN with 2 experts (not 8)
  Output: aggregate experts' outputs → [32, 4096, 4096]

Sparsity: Only 2/8 = 25% of expert parameters active per token
Memory: Still large (all experts fit in VRAM), but compute is sparse
```

**Diagram:**

```
Token: "the cat sat on the mat"

Router for "cat":
  Score expert 0 (language): 0.9 ✓ (selected)
  Score expert 1 (memory): 0.1
  Score expert 2 (code): 0.05
  Score expert 3 (reasoning): 0.3 ✓ (selected)
  Score expert 4 (math): 0.1
  ...
  
  Top-2: [expert_0, expert_3]
  
  Compute: FFN_0("cat") + FFN_3("cat")
  Output: weighted sum

Router for "sat":
  Score expert 0: 0.85 ✓
  Score expert 1: 0.3 ✓
  Score expert 2: 0.05
  ...
  
  Top-2: [expert_0, expert_1]
  
  Token "cat" uses experts [0, 3]
  Token "sat" uses experts [0, 1]
  → Different routing per token
```

---

## Load Balancing: The Key Constraint

**Problem:** If the router always selects the same experts, others are unused.

```
Without load balancing:
  Expert 0 (language): selected for 90% of tokens
  Expert 1 (code): selected for 5% of tokens
  Expert 2–7: selected for < 1% of tokens
  
  Result:
    Expert 0 GPU: 100% utilized, thermal throttle
    Expert 1 GPU: 5% utilized, idle
    Experts 2–7: barely used, wasted VRAM
```

**Solution:** Add load-balancing loss during training.

```
Auxiliary loss (used during training, not inference):

loss_balance = λ * sum_over_experts(
  (# tokens assigned to expert) * (router logits for expert)
)

Intuition: encourage router to spread tokens evenly.

During inference:
  Router still has learned to balance (from training).
  Some imbalance remains (natural variance), but much improved.
```

**Load-balancing strategies:**

```
Strategy 1: Hard assignment (deterministic routing)
  Router outputs logits → argmax top-k
  Deterministic, reproducible, fast
  Downside: gradients don't flow through non-selected experts (dead experts)

Strategy 2: Soft assignment (probabilistic routing)
  Router outputs logits → softmax
  Sample top-k experts probabilistically
  Upside: all experts receive gradient updates
  Downside: variance, slower (sampling overhead)

Strategy 3: Expert chooses tokens (token-expert affinity)
  Instead of router deciding, use attention-like mechanism
  Each expert learns which tokens it's good at
  Harder to implement, but better balance in practice
```

---

## Expert Parallelism: Multi-GPU Mapping

**Scenario:** 128 experts, 8 GPUs. How to distribute?

```
Option 1: All experts on all GPUs (data parallel)
  Pro: No expert communication, simple
  Con: 128 * 4096 * 4096 * 4 / 8 = 8 GB per GPU (tight)
  
Option 2: Shard experts across GPUs (expert parallel)
  GPU 0: experts 0–15
  GPU 1: experts 16–31
  ...
  GPU 7: experts 112–127
  
  Pro: Each GPU only loads 16 experts (~1 GB), room for large models
  Con: Route tokens to correct GPU (communication overhead)

Option 3: Hybrid (data + expert parallel)
  8 GPUs arranged as 2x4 grid
  Data parallel: 2 replicas
  Expert parallel: 4 expert shards
  Scales to very large models with manageable communication
```

**Communication pattern (expert parallel):**

```
Input tokens: [batch, seq, hidden] on GPU 0

Router on GPU 0: decide which GPU has the needed expert
  Token 1 → expert 5 (on GPU 0)
  Token 2 → expert 22 (on GPU 1)
  Token 3 → expert 5 (on GPU 0)
  Token 4 → expert 90 (on GPU 5)
  ...

AllToAll communication:
  GPU 0 sends token_2 to GPU 1, token_4 to GPU 5, etc.
  GPU 1 receives tokens destined for experts 16–31
  
  GPUs compute FFN for their experts
  AllToAll send results back to source GPUs

Bottleneck: AllToAll bandwidth = input size
  [batch, seq, hidden] * num_experts / GPUs = 32 * 4096 * 4096 / 128 ≈ 5 MB per token (if sparse routing)
```

---

## Story: Scaling a Model from 70B to 500B Parameters

**Setup:** Want to use larger models (better accuracy) but GPU memory is a constraint.

**Initial constraint:** 8x H100 GPUs, 80 GB each = 640 GB total.

**Option 1: Dense 500B model**
```
Memory needed: 500B * 2 bytes (fp16) = 1 TB
Hardware: need 16 GPUs (2x current)
Cost: 2x training compute, 2x VRAM
Latency: proportional to parameters, ~5–10x slower per token
```

**Option 2: MoE with 128 experts (sparse 500B)**
```
Experts: 128, each ~4B parameters
Active experts per token: 2 (typical)

Memory: 128 * 4B * 2 bytes = 1 TB total
  On 8 GPUs with expert parallel: 1 TB / 8 = 125 GB per GPU (tight, but fits)
  
Compute: 2 experts * 4B / 8 GPUs = 1B FLOPs per GPU per token (manageable)

Effective throughput: similar to 70B (sparse routing) but much better quality
Cost savings: 1 TB VRAM vs 1 TB (same), but same 8 GPUs work
```

**Result:**
```
Model quality: ~500B (from large model + specialization)
Inference latency: ~1–2x 70B (sparse activation helps)
Memory: fits on existing 8 GPUs
Cost per token: 1/8x (MoE with sparsity)
```

---

## When to Use MoE & Expert Parallelism

| Scenario | Use MoE? | Why |
|----------|----------|-----|
| Large models (> 100B) with memory constraints | YES | Sparse routing reduces memory/compute |
| High-throughput inference (many users) | YES | Parallelizes expert routing across tokens |
| Research (exploring model specialization) | YES | Easy to add new experts for specific tasks |
| Single small model (< 20B) | NO | Overhead of routing > benefits |
| Real-time latency-critical (< 50 ms) | MAYBE | Load imbalance causes tail latency spikes |
| Privacy-critical (each user gets dedicated expert) | NO | Routing reveals privacy info |

---

## Q&A (Real Interview Depth)

**Recall 1:** Why does MoE reduce memory and compute while maintaining model quality?

*Must-say:*
- Dense 500B: all 500B parameters active per token
- Sparse 500B MoE: only 2/128 experts active = ~1% of parameters per token
- Trade-off: specialization. Instead of one jack-of-all-trades model, 128 specialized experts
- Quality maintained because total capacity is still 500B, just distributed

*Context (trading-firm infrastructure):* "You want a 500B model but have 8x H100 budget (640 GB). MoE or offload?"

**Probe 1:** 128 experts, top-k=2. What's the average number of tokens per expert per batch of 32,000?

*Expected:*
- Total tokens: 32,000
- Each token routes to 2 experts
- Total tokens routed: 32,000 * 2 = 64,000 expert-token pairs
- Per expert: 64,000 / 128 = 500 tokens on average
- Answer: ~500 tokens per expert, but variance is high (load imbalance)

**Numeric 1:** 8 experts, expert parallel on 4 GPUs. AllToAll communication moves tokens between GPUs. Batch 32, seq_len 4096, hidden 4096. Bytes transferred?

*Working:*
- AllToAll between 4 GPUs
- Each GPU sends to 3 others
- Per GPU: 32 * 4096 * 4096 * 2 bytes / 4 (on average, sparse) ≈ 256 MB sent
- 4 GPUs * 256 MB = 1 GB total

**Numeric 2:** Training with auxiliary loss weight λ=0.01. Loss_moe = 0.1, loss_main = 10. What's the combined loss?

*Working:*
- loss_total = loss_main + λ * loss_moe = 10 + 0.01 * 0.1 = 10.001
- Auxiliary loss is tiny, just a regularizer

**Story:** Switch Transformers (Shazeer et al., 2021) showed that MoE scales to 1.6 trillion parameters on 32 TPUs while maintaining competitive accuracy. The key was careful load balancing and expert parallelism. Without load balancing, 30% of experts would be idle.

---

## Checklist & Common Pitfalls

- [ ] **Monitor expert load balance.** Some experts should be used 1–3%, not 30% of tokens.
- [ ] **Tune top-k (number of experts per token).** Top-k=1 is fastest, top-k=2–4 is typical, top-k>4 is rarely beneficial.
- [ ] **Use auxiliary loss during training.** Inference won't balance well without it.
- [ ] **Measure AllToAll bandwidth on your interconnect.** NVLink and InfiniBand have different saturation points.
- [ ] **Test load-imbalance impact on tail latency.** P99 might be 10x worse than P50 if load is unbalanced.

**Common wrong answer:** "MoE always improves throughput."
*Corrected:* "MoE improves compute efficiency (sparse routing), but communication overhead can hurt latency. Depends on interconnect and load balance."

---

## References & Next Steps

- Read Switch Transformers (Shazeer et al., 2021) for large-scale MoE training.
- Study GShard's load-balancing algorithm (Lepikhin et al., 2020).
- Profile AllToAll bandwidth on your GPU cluster.
