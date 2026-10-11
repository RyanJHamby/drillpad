# Model Memory & FLOPs Math: "Does It Fit & What's the Throughput?"

## The Problem

You have an 80B parameter model. You want to run inference on 4x H100 GPUs. Questions:

- Does it fit in GPU memory?
- How many tokens/second can we serve?
- What's the bottleneck (compute or memory)?

```
80B parameters, 4 H100s

Memory requirement: ???
  BF16: 80B params × 2 bytes/param = 160 GB
  H100 memory: 80 GB × 4 = 320 GB
  Fits! (160 < 320) ✓

Throughput: ???
  Tensor FLOPS per request: ???
  Peak H100 FLOPs: ???
  ???

Answer: Need first-principles math
```

**Why this matters:** Interviews test whether you can estimate model viability without running it. This is the core skill for ML infrastructure decisions.

---

## Memory Calculation: Parameters + Activations + KV Cache

```
Total GPU memory = Model weights + Activations + KV cache + Overhead

1. Model weights (parameters)
   80B params × 2 bytes (BF16) = 160 GB
   [or 4 bytes FP32 = 320 GB, but we'll use BF16]

2. Activations (intermediate values during forward pass)
   Rough estimate: 10-20% of weights
   80B × 0.15 (typical) = 12 GB

3. KV cache (cached keys/values for previous tokens)
   For batch_size=16, max_seq_len=4096:
   Cache = 2 × (batch × seq_len × hidden_dim × bytes/param)
   = 2 × (16 × 4096 × 12800 × 2) ≈ 4 GB
   
   (Rough: cache ≈ 2 × batch_size × seq_len / model_scale)

4. Optimizer state (if training, not inference)
   Training: weights + gradients + momentum = 2-4x model size
   Inference: minimal overhead

Total (inference): 160 + 12 + 4 + 16 (overhead) = 192 GB
Available: 320 GB (4×80GB H100s)
Conclusion: Fits with 128GB margin ✓
```

---

## FLOPs Calculation: Training vs Inference

**Training a model on N tokens:**
```
FLOPs = 6 × N × D
  (approximately 6 FLOPs per parameter per token)
  
80B parameters, 1 trillion tokens training:
  FLOPs = 6 × 1e12 × 80e9 = 4.8e23 FLOPs
  
Peak H100 FP32 throughput: 1.5e12 FLOPs/sec (approx)
Time = 4.8e23 / 1.5e12 = 3.2e11 seconds ≈ 10,000 years (single GPU)
With 8 H100s (8-way parallelism): ~1,250 years
```

**Inference on 1 token:**
```
Forward pass FLOPs ≈ 2 × D (2 FLOPs per parameter, one forward pass)
  (Simplification: matrix multiply is 2N ops)

80B parameters:
  FLOPs_per_token ≈ 2 × 80e9 = 1.6e11 FLOPs

H100 peak: 1.5e12 FLOPs/sec
Time_per_token = 1.6e11 / 1.5e12 ≈ 107 milliseconds

But: This is theoretical peak (never achieved)
Real throughput: 30-50% of peak (memory bandwidth is usually bottleneck)
Real time_per_token ≈ 200-300 milliseconds
```

---

## Memory Bandwidth vs Compute Throughput

**Roofline model (from reasoning-under-constraints/02):**

```
H100 specifications (approximate):
  Peak compute: 1.5 TFLOPS (FP32)
  Peak memory bandwidth: 3 TB/sec (HBM3)
  
Arithmetic intensity: FLOPs / Bytes

For inference on 80B model:
  FLOPs per token: 1.6e11
  Bytes read per token: 80B params × 2 bytes = 160 GB
  
  Arithmetic intensity = 1.6e11 FLOPs / 160e9 bytes = 1 FLOP/byte

Roofline analysis:
  Peak memory bandwidth = 3 TB/sec = 3e12 bytes/sec
  At 1 FLOP/byte: max throughput = 3e12 bytes × 1 FLOP/byte = 3e12 FLOPs/sec
  
  But wait, peak compute is only 1.5e12 FLOPs/sec
  So we're memory-limited: 1.5e12 / 3e12 = 50% utilization

Conclusion: Memory bandwidth is the bottleneck
  → Can't improve latency with more GPUs
  → Need better algorithms or lower precision
```

---

## Tokens/Second Throughput

```
For 80B model on 4x H100:

Single-token latency: ~200-300ms (memory-bound)

Tokens per second = 1 / latency_seconds
  = 1 / 0.25 = 4 tokens/sec (single request)

But: Batching multiple requests:
  Batch size = 64 requests
  Each request: 1 token/seq
  Process 64 tokens in parallel
  
  Latency: still ~250ms (same hardware bound)
  Throughput: 64 tokens / 0.25s = 256 tokens/sec

Serving 100 users @ 1 token/sec avg:
  Need 256 tokens/sec throughput
  4x H100 provides: ~256 tokens/sec ✓ (exact match!)
```

---

## Interview Pattern: Whiteboard Math

```
Q: "You have a 70B parameter LLM.
   Customer requests: serve 100 concurrent users.
   You have budget for 2 GPUs.
   
   Can you do it? Show your math.
   
   Assumptions:
   - BF16 precision
   - Batch size: 32
   - GPU: 80GB A100 (peak 1.2 TFLOPS, 2 TB/s memory)"

Weak answer:
  "70B doesn't fit in 80GB"
  (❌ Doesn't account for quantization or multiple GPUs)

Strong answer:
  "Let me work through the math:
  
  STEP 1: Does it fit in memory?
  
  Model weights (BF16):
    70B × 2 bytes = 140 GB
  
  GPU memory available: 2 × 80GB = 160 GB
  
  After accounting for activations (~10%) + KV cache + overhead:
    140 + 14 + 8 + 8 = 170 GB needed
    170 > 160 ✗ DOESN'T FIT
  
  Solution: Tensor parallelism
    Split model across 2 GPUs
    Each GPU holds 70B / 2 = 35B params = 70 GB
    Plus overhead: ~90GB total per GPU
    Still doesn't fit ✗
  
  Alternative: 4-bit quantization
    70B × 0.5 bytes = 35 GB
    Plus overhead: ~50 GB total
    Fits! ✓
  
  STEP 2: Throughput with quantization
  
  With 4-bit quantization:
    Effective model size: 35B
    FLOPs_per_token = 2 × 35e9 = 7e10
    
  A100 peak: 1.2 TFLOPS = 1.2e12 FLOPs/sec
  Time_per_token = 7e10 / 1.2e12 = ~60ms (theoretical)
  
  Accounting for memory bandwidth & realistic utilization (30%):
    Real time_per_token ~ 200ms
  
  Batch size = 32:
    Throughput = 32 tokens / 0.2s = 160 tokens/sec
  
  STEP 3: Is 160 tokens/sec enough?
  
  100 concurrent users, each generating text:
    Typical: 50 tokens/response (generation)
    If users stagger: 100 req/hour on average
    
    100 users × 50 tokens avg = 5,000 tokens/day
    5,000 tokens / 86,400 sec = 0.058 tokens/sec steady state
    
  Burst scenario: All 100 users request simultaneously
    100 req × 1 token (first) = 100 tokens burst
    Throughput available: 160 tokens/sec
    Can handle: 160 tokens/sec >> 100 req/s ✓
  
  STEP 4: Conclusion
  
  With 4-bit quantization + 2x A100:
    ✓ Model fits (35 GB with overhead)
    ✓ Handles throughput (160 tokens/sec > 100 req/s burst)
    ✓ Latency: ~200ms per token (acceptable)
    ✗ Trade-off: 4-bit quantization loses some accuracy
    
  Recommendation:
    - Yes, feasible with quantization
    - Monitor: accuracy degradation
    - If unacceptable, suggest 4x GPUs instead (no quantization needed)
"

Why this signals good judgment:
  - You know memory calculation formulas
  - You understand tensor parallelism as option
  - You know quantization reduces memory
  - You calculate FLOPs and throughput
  - You validate against requirements (100 users)
  - You identify tradeoffs (accuracy loss)
```

---

## Checklist: Model Sizing

- [ ] Parameter count and dtype known (80B BF16)
- [ ] Memory calculation: weights + activations + cache
- [ ] Does it fit on available GPU count?
- [ ] Scaling strategy chosen (tensor parallel, pipeline parallel, quantization)
- [ ] FLOPs per token estimated (2×D for inference)
- [ ] Bottleneck identified (memory or compute)
- [ ] Tokens/second throughput calculated
- [ ] Batch size determined from throughput requirement

## Common Wrong Answers

1. **"80B model needs 80GB of GPU memory"**
   - Parameters alone: 160 GB (BF16)
   - Plus activations and KV cache: ~200 GB total

2. **"More GPUs = more tokens/second linearly"**
   - Only if memory bandwidth is available
   - Often compute is saturated (limited by memory bandwidth)

3. **"Quantization is free"**
   - Reduces memory (good)
   - Reduces accuracy (must measure impact)

4. **"Batch size doesn't affect latency"**
   - Actually: batch size ≤ token throughput / latency
   - Larger batches can improve throughput if GPU is under-utilized

5. **"Use FP32 for accuracy"**
   - FP32 = 4 bytes/param
   - BF16 = 2 bytes/param (and similar accuracy)
   - FP32 only needed for training
