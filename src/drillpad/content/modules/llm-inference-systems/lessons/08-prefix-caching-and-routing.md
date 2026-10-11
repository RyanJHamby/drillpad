# Prefix Caching & Multi-Model Routing: Shared Prefixes and Cache Management

## The Problem: Redundant KV Computation Across Requests

When multiple requests share the same prompt prefix (e.g., multi-turn conversation, RAG system), the KV cache for that prefix is computed multiple times.

```
Example: Retrieval-Augmented Generation (RAG)

User query: "What is the capital of France?"

System:
  1. Retrieve documents: "France, officially the French Republic..."
  2. Build prompt: [SYSTEM_PROMPT] + [RETRIEVED_DOCS] + [USER_QUERY]
  
Requests A, B, C (same user, similar queries):
  Request A: [SYSTEM] + [DOC_1, DOC_2] + "What is capital?"
  Request B: [SYSTEM] + [DOC_1, DOC_2] + "What is population?"
  Request C: [SYSTEM] + [DOC_1, DOC_2] + "What is currency?"
  
Shared prefix: [SYSTEM] + [DOC_1, DOC_2] = 3000 tokens (same for all 3)

Without prefix caching:
  Request A: compute KV for all 3000 + query tokens = 3100 FLOPs
  Request B: compute KV for all 3000 + query tokens = 3100 FLOPs (same prefix!)
  Request C: compute KV for all 3000 + query tokens = 3100 FLOPs (same prefix!)
  Total: 9300 FLOPs, 9000 wasted on recomputation

With prefix caching:
  Request A: compute KV for 3100, save cache = 3100 FLOPs
  Request B: reuse KV for prefix, compute only 100 more = 100 FLOPs
  Request C: reuse KV for prefix, compute only 100 more = 100 FLOPs
  Total: 3300 FLOPs (64% savings)
```

---

## Prefix Caching: Architecture

**Idea:** Store KV cache for common prefixes, reuse across requests.

```
KV Cache Storage:

Before prefix caching (vLLM PagedAttention):
  Request A: KV pages [0–30] (3000 tokens)
  Request B: KV pages [31–61] (separate copy of 3000 token prefix)
  Request C: KV pages [62–92] (another separate copy)
  
After prefix caching:
  Shared prefix: KV pages [0–30] (cached once)
  Request A: pages [0–30] + [31–35] (prefix + unique query)
  Request B: pages [0–30] + [36–40] (same prefix, different query)
  Request C: pages [0–30] + [41–45] (same prefix, different query)
  
Memory saved: 2 * 30 pages = 60 pages = 1920 MB (assuming 32 MB per page)
```

**Implementation:** Use a hash of the prompt to identify shared prefixes.

```
Prefix hash = SHA256(prompt_text)[:32]
  Hash → cache key
  Value → KV cache pages

Lookup:
  1. Hash incoming prompt: h = SHA256(prompt)
  2. Check cache: if h in cache, load KV pages
  3. If not, compute and insert into cache

Eviction:
  LRU (least recently used) for memory management
  Keep most common prefixes (e.g., system prompt)
```

---

## Multi-Model Routing: Choosing Which Model to Use

In production, you might have multiple model sizes. Route requests based on latency/quality trade-offs.

```
Router logic:

Input: Request with prompt, latency SLO, quality requirement

Decision tree:
  1. Is prefix cached? (Yes → fast path)
     → Use large model (better quality, still fast with cache)
  2. Is latency budget tight (< 200 ms)?
     → Use small model (7B, faster, lower quality)
  3. Is quality critical (customer-facing)?
     → Use large model (70B, slower, higher quality)
  4. Default: use medium model (13B, balance)

Example: chat.openai.com
  - Quick casual queries → GPT-3.5 (small, fast)
  - Long-form writing → GPT-4 (large, slow)
  - Repeated system prompt (all requests) → cached
```

**Diagram:**

```
Request arrives
      ↓
    [ Prefix cache hit? ]
      ↙          ↘
    YES           NO
     ↓             ↓
   Fast         Compute KV
   path         (slow path)
     ↓             ↓
    [ Use large  [ Latency budget? ]
     model,        ↙           ↘
     + cache ]   Tight          Loose
                  ↓             ↓
               Small         Large
               model         model
                 ↓             ↓
              Process       Process
```

---

## Cache Management: LRU and Prefix Tokenization

**LRU eviction strategy:**

```
Cache capacity: 100 GB
Current usage: 98 GB

New request arrives, needs 5 GB:
  1. Check if 5 GB available: 100 - 98 = 2 GB (not enough)
  2. Evict least-recently-used prefixes until 5 GB free
  3. Common evictions: old conversation, old user session
  4. Keep: system prompt (used by all), recent queries

Example evictions:
  - User session from 1 hour ago: 500 MB
  - Private retrieval docs (one-time use): 2 GB
  - Old conversation turn: 300 MB
  Total freed: 2.8 GB (not quite enough)
  
  - Evict one more old session: 2.5 GB
  Total freed: 5.3 GB ✓
```

**Prefix tokenization (important for cache key):**

```
Problem: Two prompts that are semantically similar might have different tokens.

Prompt A: "What is the capital of France?"
Prompt B: "What  is  the  capital  of  France?" (extra spaces)

Without careful tokenization:
  Tokens differ → different cache keys → cache miss (wasteful)

Solution: Canonical tokenization
  1. Normalize prompt: strip whitespace, lowercase special tokens
  2. Tokenize consistently
  3. Hash first N tokens (prefix) for cache key

Example:
  Prompt A → [104, 34, 2910, 6], cache key = hash([104, 34, 2910])
  Prompt B → [104, 34, 2910, 6], cache key = hash([104, 34, 2910]) (same!)
```

---

## Story: RAG System Throughput Bottleneck

**Setup:** Document QA system. Query: "What are the main points of document X?" with the full document as context.

**Without prefix caching:**
```
Retrieval: 5000 tokens (document)
Query: 100 tokens
Total per request: 5100 tokens

Request arrives every 200 ms (average)
Throughput: 1 request per 200 ms = 5 req/sec

Processing time per request:
  5100 tokens * (0.2 ms / token) = 1.02 sec
  (on H100 with batching, ~5000 tokens/sec throughput)
  
Budget: 200 ms between requests, but each takes 1+ sec
→ Queue backs up, tail latency spikes
```

**With prefix caching:**
```
Request 1:
  - Retrieve document (same for all)
  - Tokenize prefix (5000 tokens)
  - Compute KV, cache it
  - Compute query (100 tokens)
  - Time: 5100 tokens * (0.2 ms) = ~1 sec

Request 2–10 (same document, different questions):
  - Prefix cache hit (5000 tokens)
  - Only compute query (100 tokens)
  - Time: 100 tokens * (0.2 ms) = ~20 ms

Average time (10 requests, 1 cold + 9 warm): 
  (1000 + 9*20) / 10 = 110 ms per request ✓

Throughput improves by 9x.
```

---

## When to Use Prefix Caching

| Scenario | Use Prefix Caching? | Why |
|----------|-------|-----|
| Multi-turn conversation (same system prompt) | YES | System prompt cached for all turns |
| RAG system (same retrieval docs) | YES | Document context reused across queries |
| High-concurrency chat (many users) | YES | Shared system prompts, even if different topics |
| Few long unique requests (no repeats) | NO | Cache overhead > benefits |
| Real-time (low tolerance for stale cache) | MAYBE | Cache might return outdated results (mitigated by TTL) |
| Privacy-critical (data isolation) | MAYBE | Cache might leak prompts across users (need isolation) |
| Streaming (token-by-token response) | YES | Cache latency hidden by streaming |

---

## Q&A (Real Interview Depth)

**Recall 1:** Why does prefix caching improve throughput in RAG systems?

*Must-say:*
- Without caching: every request computes KV for document + query.
- With caching: first request pays cost, subsequent requests reuse.
- Amortized cost over N requests: (1 * compute_doc + N * compute_query) / N.
- For large documents: compute_doc >> compute_query, so savings ≈ compute_doc / N.

*Context (Anthropic Claude):* "Our system handles millions of RAG queries daily. The retrieval corpus is 10M documents. Which prefixes should we cache?"

**Probe 1:** You cache prefixes with TTL (time-to-live) of 1 hour. A user asks 100 queries in an hour. How many cache hits do you expect?

*Expected:*
- First 10 queries (different documents): likely misses or hits only on system prompt.
- Queries 11–100 (same document topic, or re-used docs): hits.
- Real answer: depends on query distribution. If 70% of queries use top 100 documents, you get ~60% hit rate after warm-up.

**Numeric 1:** Cache capacity: 100 GB. System prompt: 1 MB. Average document: 5 MB. Average unique prefix per user: 20 MB. How many unique prefixes fit?

*Working:* (100 GB - 1 MB) / 20 MB ≈ 5000 unique prefixes.

**Numeric 2:** Request for 10-token query, 1000-token prefix. Without cache: 1010 tokens to compute. With cache: 10 tokens. Latency 100 µs per token. Time saved?

*Working:*
- Without: 1010 * 100 µs = 101 ms
- With: 10 * 100 µs = 1 ms
- Saved: 100 ms

**Story:** OpenAI's ChatGPT uses prefix caching for system prompts. Every user request includes the same system instructions (thousands of tokens). Without caching, they'd waste 80% of compute on redundant KV. Caching reduced their inference cost by ~60% (measured in token throughput per dollar).

---

## Checklist & Common Pitfalls

- [ ] **Measure cache hit rate, not just capacity.** You might cache efficiently but have low hit rate if prefixes are unique.
- [ ] **Use canonical tokenization.** Small differences in whitespace shouldn't cause cache misses.
- [ ] **Set TTL appropriately.** Too short = evictions, too long = stale results.
- [ ] **Isolate caches by user/tenant.** Don't leak prefixes across security boundaries.
- [ ] **Monitor memory usage.** Cache can bloat uncontrollably without proper eviction.

**Common wrong answer:** "Prefix caching always saves 50%+ compute."
*Corrected:* "Savings depend on prefix overlap. If all requests are unique, savings are minimal. If all share system prompt (1% of compute), savings are 1%."

---

## References & Next Steps

- Read OpenAI's tokenizer documentation (how they handle multi-request caching).
- Implement LRU eviction for a simple KV cache.
- Profile your inference system: what prefixes are most common?
