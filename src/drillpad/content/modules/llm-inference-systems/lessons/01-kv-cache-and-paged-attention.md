# KV-Cache Bottleneck and PagedAttention

## The Problem: KV-Cache Explosion

In transformer decoding, for each output token, you compute attention over all previous tokens. The K and V matrices grow linearly with sequence length.

```
Sequence length N = 4096 (typical), batch size B = 128, hidden dim = 4096

K matrix shape: [N, B, 4096] = 4096 * 128 * 4096 * 2 bytes (fp16) = 4.3 GB per request
V matrix shape: [N, B, 4096] = 4.3 GB
Total per request: 8.6 GB

Memory wall: At 100 req/s, you'd need to move 860 GB/s of memory just for KV reads.
GPU memory bandwidth (H100): ~3.3 TB/s. You hit 26% capacity on KV alone, and that's only one operation.

Worse: After generating one token, the next token reads ALL the K/V again (same data) +
the one new token's K/V. Redundant reads dominate latency, not computation.
```

**Real measurement (vLLM paper, NVIDIA A100):**
- Prefill (compute-bound): 60% peak FLOPs, limited by compute.
- Decode (memory-bound): 10% peak FLOPs, limited by KV reads.

Decode is **6x worse** in utilization because of memory bottleneck.

---

## PagedAttention: Virtual Memory for KV

Instead of one contiguous K/V matrix, split it into **pages** (e.g., 16 tokens per page).

```
Sequence: token 0, 1, 2, ..., 4095

Without PagedAttention (fragmented allocation):
  malloc() for token 0's KV:    2 MB
  malloc() for token 1's KV:    2 MB (different address)
  malloc() for token 2's KV:    2 MB (different address)
  ... 4096 times
  Total: fragmented across GPU memory, non-contiguous reads, cache misses.

PagedAttention (paged):
  Page 0: tokens 0–15 (32 MB)
  Page 1: tokens 16–31 (32 MB)
  ...
  Page 255: tokens 4080–4095 (32 MB)
  
  Attention kernel reads pages contiguously. Within a page, all 16 tokens' K/V are adjacent.
  GPU cache (L2, shared memory) hits on multiple tokens per cache line.
```

**Benefit: Memory bandwidth efficiency.**
- Contiguous reads reduce cache misses.
- Fewer TLB (translation lookaside buffer) misses.
- Vectorized loads (load 128 bytes in one instruction, not scattered).

**Measured speedup (vLLM):** 24x throughput increase on decode on a single GPU (2.3 req/s → 52 req/s for 4K sequence length on A100).

---

## Block Allocation and Memory Reuse

Pages enable **block reuse** (memory pooling for KV).

```
Request 1 (prompt tokens 0–100):
  Allocates pages 0–6 (7 pages * 32 MB = 224 MB)

Request 2 arrives (while Request 1 is still decoding):
  Allocates pages 7–10 (for its 100 prompt tokens)
  Request 1's pages stay allocated.

Request 1 finishes decoding 50 tokens:
  Final sequence: 0–149 (100 prompt + 50 generated)
  Pages 0–9 allocated (10 pages)

Request 2 finishes decoding 75 tokens:
  Final sequence: 0–124 (100 prompt + 24 generated... wait, let me redo this)

Actually, let me be clearer:

Request 1:
  Allocates blocks [0, 1, 2] for prompt (100 tokens = 3.125 pages, round up to 3)
  Decodes and reuses same blocks (block 3, 4, 5, 6 as KV grows)
  Final: 150 tokens = 10 blocks used

Request 2:
  Arrives after Request 1 started decoding
  Allocates blocks [10, 11, 12] for prompt
  Can't reuse Request 1's blocks (different sequence)

When Request 1 finishes:
  Blocks [0–9] are freed and returned to the pool
  Request 3 can immediately reuse them

Key insight: Without PagedAttention, every request allocates a full N-sized matrix upfront (4096 * 4096 * fp16 = huge). With paging, you allocate blocks on-demand and can reuse them across requests.
```

**Real impact:** Enables batching. Without paging, batch size is limited by GPU memory per-request overhead. With paging, you can run 10x more concurrent requests on the same GPU.

---

## Attention Kernel Implementation

The kernel needs to handle **irregular access patterns** (requests with different sequence lengths in the same batch).

```
Input: 
  Queries: [batch_size, head_num, q_len, head_dim] (current token only: q_len=1)
  Keys/Values: scattered across pages (block_table tells you where they are)
  block_table[i] = [page_id_0, page_id_1, page_id_2, ...] (pages for request i)

Algorithm (CUDA kernel):
  for each query token q (1 token per request in decode):
    for each page in the request's block_table:
      load K, V from page
      compute attention score = Q @ K^T
    softmax(scores)
    output = softmax @ V

Challenge: Memory layout.
  Page 0 contains tokens 0–15 of request A's KV.
  Page 1 contains tokens 0–15 of request B's KV (if request B has a page, else request A's next page).
  The kernel must avoid reading request A's page 0 when computing attention for request B.
  
  Solution: block_table[request_id] tells the kernel which physical pages belong to which request.
  The kernel becomes a gather operation: scattered physical pages → contiguous logical sequence.
```

**Latency impact:** Gathering adds ~10–20% overhead vs. contiguous access, but the bandwidth savings (24x) far outweigh it.

---

## Q&A (Real Interview Depth)

**Recall 1:** Explain why decode throughput is memory-bound while prefill is compute-bound.

*Must-say:*
- Prefill: N input tokens → 1 output token. Batch size N is large, matmul is Ω(N³) in hidden dim. Compute dominates.
- Decode: 1 input token → 1 output token. Matmul is small (1 * d^2 where d ~ 4K). Each token reads all previous K/V (4K tokens * 4K dims * 2 matrices = ~64 GB of memory for one attention step). Memory read >> computation.

*Interview-style context:* "Your inference service handles prefill and decode separately. How do you schedule them to avoid stranding GPUs?"

**Probe 1:** You batch 128 requests in decode, each with 4K sequence length. You have 40 GB GPU memory. Do they all fit?

*Calculation:*
- Per request: 4096 tokens * 4096 hidden * 2 (K, V) * 2 bytes (fp16) = 67 MB
- 128 requests * 67 MB = 8.6 GB
- All fit (40 GB > 8.6 GB), but only if you use PagedAttention.
- Without paging, you'd allocate contiguous matrices and fragment → often OOM even though total is < 40 GB.

*Answer:* "Yes, they fit with PagedAttention's block pooling. Without it, you'd have memory fragmentation and couldn't run more than 30–40 requests."

**Numeric 1:** PagedAttention pages are 16 tokens. A request has 1024 tokens in the KV cache. How many pages?

*Working:* 1024 / 16 = 64 pages.

**Numeric 2:** KV cache per token: 4096 hidden dim * 2 (K, V) * fp16 = 16 KB per head. With 32 heads, that's 512 KB per token. At 100 req/s with avg 4K sequence, how much KV memory is allocated per second (assuming no reuse)?

*Working:* 100 req/s * 4K tokens * 512 KB/token = 204.8 GB allocated per second. Huge. PagedAttention's reuse across requests drops this by 10–50x.

**Story:** vLLM's PagedAttention (2023) was a breakthrough because traditional systems allocated K/V upfront. With paging, you pay on-demand. One fix enabled 24x throughput. This is the kind of leverage that matters in agent-sandbox platforms (sharing paged blocks across sandboxed agent instances).

