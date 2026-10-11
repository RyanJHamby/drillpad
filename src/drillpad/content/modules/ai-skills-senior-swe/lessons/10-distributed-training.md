# Distributed Training Infrastructure: FSDP, ZeRO, Tensor Parallelism

## Why This Interview Matters

If you're interviewing at an AI lab (Anthropic, Together, Hugging Face) or building training infra, distributed training is non-negotiable. This isn't just inference — it's the systems work that makes training large models economical.

**Core insight:** GPUs can't communicate as fast as they compute. Every training parallelism strategy is a tradeoff between memory, communication, and compute.

## The Problem: Why Distribution Is Hard

```
Single GPU:
  Model weights: 70B parameters = ~140GB (in float32)
  A100 has 80GB memory.
  Model doesn't fit.
  
  Even if it did, you're stuck at one GPU's training speed.

Multiple GPUs:
  Now you need to coordinate:
    - Move data to each GPU
    - Compute gradients in parallel
    - Average gradients (AllReduce)
    - Update weights with averaged gradients
    
  AllReduce is the bottleneck. NVLink is fast (600GB/s) but model 
  communication is expensive. This is why parallelism strategy matters.
```

## Three Core Strategies (Know These Cold)

### 1. Data Parallelism (DDP)

```
Setup:
  Each GPU gets a full model copy
  Each GPU processes different data
  After each batch, average gradients (AllReduce)
  
Memory per GPU: 140GB (full model)
Communication: Gradients only (~140GB per AllReduce)

Pros:
  - Simple (each GPU is nearly independent)
  - Scales well until communication dominates

Cons:
  - Model must fit on one GPU
  - Limited by single-GPU memory

When to use:
  - Models < 80GB (fits on a single A100)
  - You have a lot of GPUs (communication cost is acceptable)
```

### 2. FSDP (Fully Sharded Data Parallel)

```
Setup (conceptually):
  Each GPU holds only a shard of:
    - Model parameters (1/8 of weights)
    - Gradients (1/8 of gradients)
    - Optimizer state (1/8 of optimizer)
    
  To do forward pass:
    1. Gather shard from all GPUs
    2. Compute forward on full model
    3. Scatter shards back
    
Memory savings: ~8x (for 8 GPUs)
Communication: More frequent but smaller chunks

Pros:
  - Models that didn't fit now do (70B fits across 8x A100s)
  - Good memory/compute balance

Cons:
  - More communication overhead
  - Requires careful implementation

When to use:
  - Model 80-500GB (doesn't fit on one GPU, fits on a cluster)
  - You want the simplicity of data-parallel training

Real example:
  70B model training on 8x A100 cluster
  FSDP: ~17.5GB per GPU (70B / 8, plus sharded optimizer state)
  Beats data parallelism (140GB per GPU won't fit)
```

### 3. Tensor Parallelism

```
Setup:
  Individual weight matrices are split across GPUs
  Example: Linear layer [8192 x 8192] split as [8192 x 1024] per GPU
  
  Forward pass: gather inputs, compute matmul on shard, scatter outputs
  
Pros:
  - Reduces latency per inference (smaller matrices)
  - Good for inference serving

Cons:
  - Requires NVLink (fast intra-node communication)
  - Can't span nodes efficiently
  - Complex to implement

When to use:
  - Single node (8 GPUs on one machine)
  - You care about latency per token (inference, not training)
```

## Interview Pattern: Design a Training Run

```
Q: "Design infrastructure to fine-tune a 70B model on 100M tokens.
   You have access to an 8-GPU cluster with A100s."

Setup:
  - Model: 70B parameters = ~140GB (FP32) or 70GB (FP16)
  - Data: 100M tokens (fits in GPU memory as batches)
  - Hardware: 8x A100 (80GB each) with NVLink

Weak answer:
  "Use data parallelism with PyTorch DDP"
  (❌ Model doesn't fit: 140GB/8 = 17.5GB per GPU, but you have 8 GPUs
      not 1, and 140GB / 8 = 17.5GB is wrong math)

Strong answer:
  "Strategy:
  
  1. Memory budget
     - Model: 70B FP16 = 140GB (weights + activations)
     - Per-GPU: 140GB / 8 = 17.5GB per GPU
     - Leaves ~60GB per GPU for activations, optimizer state
  
  2. Parallelism choice: FSDP
     - Each GPU: 1/8 model parameters, 1/8 gradients, 1/8 optimizer state
     - FSDP gathers before forward, scatters after
     - Overhead: more communication, worth it for this model size
  
  3. Training loop
     - Batch size per GPU: 8 (fits in remaining memory)
     - Global batch size: 8 * 8 = 64
     - Steps to 100M tokens: 100M / (64 * seq_len)
  
  4. Actual implementation
     - PyTorch FSDP with ZerO-1 (optimizer state sharded)
     - Gradient checkpointing to save memory
     - Mixed precision (FP16 compute, FP32 master weights)
  
  5. Expected performance
     - A100 at ~312 TFLOPs (theoretical)
     - 70B model needs ~140T ops per forward/backward
     - Per GPU: ~17.5T ops
     - Expect ~50-100 samples/sec depending on overhead
     - 100M tokens at 8x seq_len=512: ~24M samples
     - Runtime: ~240K-500K seconds ≈ 3-6 days
  
  6. Failure modes to watch
     - CUDA OOM (ran out of memory mid-forward pass)
     - Slow gradient communication (check NVLink bandwidth)
     - Imbalanced data loading (some GPUs wait for others)
  
  Tooling:
    - PyTorch + FSDP for training
    - Deepspeed ZeRO as alternative (usually faster in practice)
    - Wandb or Tensorboard for monitoring
  
  If this were 1T parameters instead of 70B:
    - Would need tensor parallelism on top of FSDP
    - Or move to a larger cluster (this 8-GPU setup can't scale that far)
  "

Why this signals good judgment:
  - You did the math (model size, memory per GPU, steps to data)
  - You picked a parallelism strategy with justification
  - You knew the actual tools (FSDP, Deepspeed, gradient checkpointing)
  - You thought about failure modes
  - You could estimate runtime realistically
```

## Key Concepts You'll Be Asked About

| Concept | Why It Matters | Interview Ask |
|---|---|---|
| **Gradient checkpointing** | Trade compute for memory (recompute activations instead of storing them) | "How do you fit a 70B model on 8x A100s?" |
| **Mixed precision** | FP16 compute (fast), FP32 master weights (stable) | "Why not just use FP16 everywhere?" |
| **Communication bottleneck** | AllReduce is expensive; ZeRO-3 minimizes it | "How does FSDP vs. Deepspeed ZeRO differ?" |
| **Activation recomputation** | Recompute forward activations during backward (saves memory, costs compute) | "Design a memory-constrained training run" |
| **Microbatching** | In pipeline parallelism, batch into smaller chunks to hide pipeline bubbles | "How do you avoid idle GPUs in pipeline parallelism?" |

## What This Signals

- You understand systems-level tradeoffs (memory vs. compute vs. communication)
- You can estimate performance realistically (not just "it will be fast")
- You know the actual tools used in production (FSDP, Deepspeed, not just theory)
- You think about failure modes (OOM, slow communication, data bottlenecks)

In AI lab interviews specifically, this is a core assessment: "Can you think through a training infrastructure problem end-to-end?"
