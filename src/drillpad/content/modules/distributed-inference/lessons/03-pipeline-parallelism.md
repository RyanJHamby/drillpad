# Pipeline Parallelism: GPipe, Micro-Batching, Bubble Overhead

## Vertical Slicing: Stages Across GPUs

Instead of sharding weights horizontally (tensor parallelism), split the network vertically (layers).

```
70B model, 80 layers

Tensor Parallelism (horizontal):
  GPU 0-3: layers 0-80 (each GPU has full layers, but weights sharded)

Pipeline Parallelism (vertical):
  GPU 0: layers 0-20
  GPU 1: layers 21-40
  GPU 2: layers 41-60
  GPU 3: layers 61-80
  
  Each GPU has full weights for its layers (no AllGather needed).
  But data must flow sequentially through GPUs.
```

**Advantage:** No AllGather overhead, only point-to-point data transfer (output of layer 20 → input of layer 21).

**Disadvantage:** Sequential dependency (GPU 1 must wait for GPU 0 to finish).

---

## Naive Pipeline: Bubble Overhead

```
Timeline (4 GPUs, 4 mini-batches):

Naive (each mini-batch fully completes before next):
  GPU 0: [mbatch 1] [mbatch 2] [mbatch 3] [mbatch 4]
  GPU 1: wait    [mbatch 1] wait    [mbatch 2] wait    [mbatch 3] wait    [mbatch 4]
  GPU 2: wait    wait    [mbatch 1] wait    wait    [mbatch 2] wait    wait    [mbatch 3] wait    wait    [mbatch 4]
  GPU 3: wait    wait    wait    [mbatch 1] wait    wait    wait    [mbatch 2] wait    wait    wait    [mbatch 3] wait    wait    wait    [mbatch 4]

GPU 1 bubbles: 3 units (waiting for GPU 0)
GPU 2 bubbles: 6 units
GPU 3 bubbles: 9 units
Total idle: 18 time units out of 36 = 50% idle

Utilization: 50%
```

---

## GPipe: Overlapping via Micro-Batching

Split each mini-batch into smaller micro-batches. Process pipelined.

```
Timeline (4 GPUs, 4 mini-batches split into 2 micro-batches each = 8 micro-batches total):

Pipelined:
  GPU 0: [mb1_μ1] [mb1_μ2] [mb2_μ1] [mb2_μ2] [mb3_μ1] [mb3_μ2] [mb4_μ1] [mb4_μ2]
  GPU 1:      [mb1_μ1] [mb1_μ2] [mb2_μ1] [mb2_μ2] [mb3_μ1] [mb3_μ2] [mb4_μ1] [mb4_μ2]
  GPU 2:           [mb1_μ1] [mb1_μ2] [mb2_μ1] [mb2_μ2] [mb3_μ1] [mb3_μ2] [mb4_μ1] [mb4_μ2]
  GPU 3:                [mb1_μ1] [mb1_μ2] [mb2_μ1] [mb2_μ2] [mb3_μ1] [mb3_μ2] [mb4_μ1] [mb4_μ2]

GPU 1 bubbles: only 1 unit (first micro-batch setup)
GPU 2 bubbles: 2 units
GPU 3 bubbles: 3 units
Total idle: 6 time units out of 32 = 18% idle

Utilization: 82%
```

**Bubble overhead:** M = # GPUs, B = # micro-batches
- Ideal (B >> M): bubble ≈ M / (M + B) ≈ 0 (good)
- Real (B = M): bubble ≈ 50% (bad)

---

## Backward Pass Complexity

Pipeline parallelism training requires storing activations for backward pass.

```
Forward pass micro-batch mb1_μ1:
  Intermediate activations: a0, a1, a2, a3 (one per layer)
  Size: 4 * [batch, seq, hidden] = 4 * 1 GB = 4 GB

Forward pass all 8 micro-batches:
  Total activations: 8 micro-batches * 4 GB = 32 GB (memory for backward)

On 4 GPUs: 32 GB / 4 = 8 GB per GPU (manageable)
But if batch splits further (16 micro-batches): 16 * 4 GB = 64 GB total (memory explosion)

Recomputation (to save memory):
  Don't store activations; recompute them during backward.
  Trade: memory (8 GB saved) for computation (2x slower backward).
```

---

## Q&A

**Recall 1:** Why does naive pipeline parallelism have bubble overhead? How does GPipe reduce it?

*Answer:* Naive: GPU 1 waits for GPU 0 to fully finish one mini-batch before starting. This creates sequential delays (bubble). GPipe splits mini-batches into micro-batches and pipelines them; while GPU 0 processes micro-batch 2, GPU 1 can process micro-batch 1. Reduces bubble from 50% to ~O(M/(M+B)) where M is # GPUs, B is # micro-batches.

**Numeric 1:** 8 GPUs, 16 micro-batches. What's the bubble overhead percentage?

*Working:* Bubble = 8 / (8 + 16) = 8 / 24 = 33%. Not bad, but could be better with more micro-batches (though memory cost increases).

**Probe 1:** You use pipeline parallelism for a 70B model across 8 GPUs. Backward pass requires 64 GB of stored activations. Your GPU is 80 GB. How do you fit weights + activations?

*Expected:* Either recompute (compute activations again on backward, save memory), or use gradient checkpointing (store every N-th activation, recompute the rest). Or reduce micro-batch size (fewer activations to store).

