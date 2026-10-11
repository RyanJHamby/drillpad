# RAG and Vector Databases: When to Use, When to Avoid, Hybrid Search

## The Core Decision: RAG vs. Long-Context Stuffing

Three years ago: RAG was the only way to handle large document collections.

Today (2026): Long-context is so cheap that "just put it in context" beats RAG for mid-size corpora.

```
Rule of thumb shift:
  Old: Use RAG for anything > 50K tokens
  Now: Use long-context-stuffing up to 1M tokens, then RAG
```

This changes interviews: "Design a retrieval system" now requires deciding whether retrieval is needed at all.

## When Long-Context Stuffing Actually Wins

```
Corpus: 500K tokens (about 100 documents, each ~5K tokens)

Option A: RAG
  - Embed documents (cost: 0.01¢ per 1K tokens)
  - Store in vector DB
  - At query time: retrieve top-K, stuff in context
  - Latency: retrieval lookup + embedding query + model call
  - Risk: retrieval quality (bad recall → model doesn't see relevant docs)

Option B: Long-context stuffing
  - No embedding, no vector DB
  - At query time: dump all 500K tokens + query in context
  - Latency: just the model call
  - Cost: 500K tokens input per call (but cached!)
  - Risk: model has more noise to filter

Winner: Long-context usually, if you can cache the corpus.
  - Prompt caching makes the 500K tokens nearly free after first call
  - Simpler (no vector DB, no embedding, no retrieval quality issues)
  - Same accuracy or better (model sees everything)
```

## When RAG Is Still Better

```
Case 1: Huge corpus (10M+ tokens)
  - Long-context-stuffing becomes expensive per call
  - RAG: retrieve top-K relevant docs, stay under context limit

Case 2: Documents change frequently
  - Long-context: need to re-cache every change (expensive)
  - RAG: update vector DB, cache stays small

Case 3: You need to explain *which source* the answer came from
  - Long-context: model hallucinated which doc, or you have to parse
  - RAG: tool call returned source explicitly
```

## Interview Pattern: Retrieval System Design

```
Q: "Design a retrieval system for a 100-document FAQ.
   Each document is ~5K tokens. Users ask questions about them."

Setup:
  - Corpus: 100 docs × 5K tokens = 500K tokens
  - Queries: "How do I reset my password?"
  - Scale: 1000 queries/day

Weak answer:
  "Build a vector database with embeddings"
  (❌ Over-engineered, ignores the option of just stuffing)

Strong answer:
  "Decision tree:
  
  1. Is the corpus static or frequently updated?
     - Static (FAQ) → long-context-stuffing is viable
     - Changing → RAG is better (don't re-embed/cache everything)
  
  For static FAQ:
    Long-context approach:
    - Concatenate all 100 docs (500K tokens)
    - Create system prompt:
      'You are a FAQ assistant. Answer from the docs below.
       [All 100 docs here]
       User question: ...'
    - Enable prompt caching
    
    Cost per query:
      First query: 500K input tokens (cache miss) = ~$0.50
      Subsequent queries: 500K cached = ~$0.005
      At 1000/day, mostly cached = ~$5/day
  
  2. If corpus grows to 10M tokens:
     Switch to RAG
     - Embed docs (one-time cost)
     - Store in vector DB (Qdrant, Weaviate, pgvector)
     - Query: retrieve top-K relevant, stuff those K in context
  
  3. If retrieval quality matters:
     Hybrid search
     - BM25 (keyword) + semantic (embeddings)
     - Combine results, re-rank
     - Better recall than either alone
  
  Implementation choice:
    If corpus < 1M tokens: long-context + caching
    If corpus 1-100M tokens: semantic search (embeddings)
    If corpus > 100M tokens: BM25 first-pass + semantic re-rank
  
  Why this approach:
    - Simplest first (long-context)
    - Scale to complexity only when needed
    - Use caching to minimize cost
    - Hybrid search for quality when corpus is large
  "

Why this signals good judgment:
  - You didn't default to RAG
  - You did the math (cost of embedding vs. context)
  - You considered tradeoffs (freshness, scale, quality)
  - You know caching changes the economics
  - You have a decision tree, not a single solution
```

## Hybrid Search: The Production Approach

When corpus is large (1M+ tokens) and quality matters:

```
1. BM25 (keyword search)
   Pros: Fast, good for exact terms, no embedding cost
   Cons: Misses semantic similarity
   
2. Semantic (vector embedding)
   Pros: Understands meaning, good for paraphrase queries
   Cons: Slower, embedding cost, retrieval quality depends on model

Hybrid:
   Run both, combine with RRF (Reciprocal Rank Fusion)
   
   BM25 returns: [doc1, doc3, doc7, ...]
   Semantic returns: [doc2, doc1, doc5, ...]
   
   RRF score = 1/(rank_bm25 + 1) + 1/(rank_semantic + 1)
   Final ranking: doc1 (score 2.0), doc2 (1.5), doc3 (1.33)
   
   Result: Better recall than either alone
```

## Common Mistakes

| Mistake | Cost | Fix |
|---|---|---|
| Embedding 10M tokens at query time | $0.10 per query vs. $0.001 with cache | Cache embeddings, pre-compute |
| RAG for 100-token corpus | Overkill, adds latency | Just stuff in context |
| Poor retrieval, then blame the model | Model gets bad context, can't answer | Fix retrieval quality, not the model |
| Not re-ranking retrieved docs | Model sees noisy results | LLM-as-judge or BM25 re-ranking |
| Assuming semantic > keyword | Semantic is good, not always better | Hybrid search for production |

## What This Signals in Interviews

- You understand RAG is a tool, not a requirement
- You can estimate when caching changes the tradeoff
- You know the actual algorithms (BM25, embedding, RRF)
- You think about scale (when to switch from stuffing to retrieval)
- You're pragmatic, not dogmatic (use simplest thing that works)

This is increasingly asked because companies built RAG systems they didn't need, then had to rip them out when long-context got cheaper. Being the person who says "just stuff it, it's cheaper" is valuable.
