# Multi-LoRA Adapter Serving

## LoRA (Low-Rank Adaptation)

```
Fine-tune LLM without changing weights:
  W_new = W_original + α * (A @ B)
  
  A: d_model × r (r small, e.g., 8)
  B: r × d_out
  
  Advantage:
    ├─ Original W: frozen (shared)
    ├─ A, B: small (LoRA rank r = 1% of model)
    ├─ Store per-customer LoRA separately
    └─ Memory: model + many small LoRA
```

## Batch LoRA Inference

```
Request 1: customer_A (LoRA_A)
Request 2: customer_B (LoRA_B)
Request 3: customer_A (LoRA_A)

Naive:
  ├─ Request 1: load LoRA_A, inference, unload
  ├─ Request 2: load LoRA_B, inference, unload
  ├─ Request 3: load LoRA_A, inference, unload
  └─ Constant loading (slow!)

Batched:
  ├─ Batch 1: [Req1, Req3] (same LoRA_A)
  │   ├─ Load LoRA_A once
  │   ├─ Process both with same adapter
  │   └─ Faster (amortize load cost)
  
  ├─ Batch 2: [Req2]
  │   ├─ Load LoRA_B
  │   └─ Process
  
  Cost:
    ├─ Without batching: 3 loads
    ├─ With batching: 2 loads (33% reduction)
```

## Scheduling

```
Queue:
  Req(LoRA_A, bsz=2)
  Req(LoRA_B, bsz=1)
  Req(LoRA_A, bsz=3)

Schedule option 1 (FCFS):
  1. Process Req1 (load A, bsz=2)
  2. Process Req2 (load B, bsz=1)
  3. Process Req3 (load A, bsz=3)
  Loads: 3

Schedule option 2 (group by LoRA):
  1. Process Req1 + Req3 together (batch, load A once, bsz=5)
  2. Process Req2 (load B, bsz=1)
  Loads: 2

Cost:
  ├─ Load time: 10ms per LoRA
  ├─ Option 1: 30ms loading
  ├─ Option 2: 20ms loading
  └─ Gain: 10ms (10% if compute time 100ms)
```

---

## Interview Checklist

- [ ] LoRA: separate small adapters per customer
- [ ] Batching by LoRA type (grouping)
- [ ] Loading cost: amortized across batch
- [ ] Scheduling: maximize batching

## Common Wrong Answers

- ❌ "Load/unload per request" — thrashing
- ❌ "Ignore LoRA affinity" — bad batching
- ❌ "Memory unlimited" — LoRA + model still costly
