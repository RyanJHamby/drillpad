# Mock Interview: Debug Slow LLM Inference

## Prompt

"Your LLM inference service is responding in 5 seconds. Goal is <1 second. You have 20 minutes to diagnose. Walk me through your debugging process."

---

## Time Plan

```
0-2 min:   Clarify setup (model size, hardware, batch size)
2-8 min:   Identify bottleneck (profile the system)
8-15 min:  Deep dive (what's actually slow?)
15-20 min: Propose fix & tradeoffs
```

---

## Scoring Rubric

**Questioning (20%)**
- [ ] Asked about model (size, quantization)
- [ ] Asked about hardware (A100? CPU inference?)
- [ ] Asked about latency breakdown (prefill vs decode)

**Diagnosis Method (30%)**
- [ ] Used profiler (Torch Profiler, nsys)
- [ ] Checked GPU utilization
- [ ] Identified: compute-bound vs memory-bound?
- [ ] Reasonable hypothesis

**Root Cause (25%)**
- [ ] Found actual bottleneck (e.g., memory bandwidth)
- [ ] Explained why (e.g., KV cache thrashing)

**Solution (15%)**
- [ ] Proposed fix aligned to root cause
- [ ] Explained tradeoff (cost vs latency)
- [ ] Realistic timeline

**Communication (10%)**
- [ ] Explained thinking clearly
- [ ] Handled unknowns gracefully

---

## Scenario Outline

```
Setup (facts given):
  Model: Llama-70B
  Hardware: A100 (80GB)
  Batch: 1 (single user requests)
  Current latency: 5 sec
  Target: <1 sec

Question 1: What profiling have you done?
  Candidate should ask:
    - Torch Profiler output?
    - GPU utilization (nvidia-smi)?
    - Breakdown: prefill (prompt) vs decode (generation)?

Revealing info (as they ask):
  Profiler shows:
    - Prefill: 100ms (prompt processing)
    - Decode: 4.9 sec for 100 tokens (49ms per token!)
    - GPU util: 20% (idle!)
    - Memory BW: 100GB/sec (model uses 900GB/sec peak)

Root cause:
  Memory bandwidth limited (not compute)
  KV cache thrashing (revisiting same memory repeatedly)

Solutions:
  1. Smaller model (4x faster, lower quality)
  2. Quantization (int8 reduces memory, 2x speedup)
  3. KV cache optimization (compression, pruning)
  4. Batch multiple requests (amortize memory load)
```

---

## 5 Follow-Up Probes

**Probe 1:** "If GPU utilization is only 20%, why not just run faster?"

*Expected:*
  - GPU does have spare compute
  - But memory bandwidth is bottleneck (GPU waiting for data)
  - Can't parallelize memory access (physics limited)

*Weak:*
  - "We should, but we can't"

**Probe 2:** "Quantization to int8 — what's the quality impact?"

*Expected:*
  - Usually <1% accuracy loss (acceptable)
  - Depends on model (some robust, some not)
  - Trade: 2x speedup for <1% quality loss (worth it)

**Probe 3:** "Can you batch requests to improve throughput?"

*Expected:*
  - Yes, if not latency-sensitive (e.g., offline processing)
  - Batch 32: 32 tokens per user per token-step
  - Amortizes memory load across users
  - Tradeoff: latency per request increases (but throughput ↑↑)

**Probe 4:** "What if the model was smaller (7B instead of 70B)?"

*Expected:*
  - KV cache smaller: 1/10 the memory
  - Same prefill+decode time, less memory
  - Speedup proportional to memory reduction (4x)
  - Tradeoff: lower quality

**Probe 5:** "Can you test these fixes quickly?"

*Expected:*
  - Quantization: quick (1 hour, PyTorch quantize_int8)
  - Smaller model: quick (load different checkpoint)
  - Batching: medium (requires request queueing)

---

## Preparation Links

- [Observability & Debugging](/learn?m=observability-debugging)
- [GPU Profiling & NCCL](/learn?m=observability-debugging&l=05-gpu-profiling-and-nccl-debugging)
- [LLM Inference Systems](/learn?m=llm-inference-systems)
- [Memory Optimization](/learn?m=memory-optimization)
