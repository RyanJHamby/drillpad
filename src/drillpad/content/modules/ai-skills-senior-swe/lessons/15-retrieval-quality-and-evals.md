# Retrieval Quality and Evals: Hybrid Search, Reranking, Metrics

## Why This Interview Matters

RAG (Retrieval-Augmented Generation) is everywhere: chatbots, search, question-answering systems. **But retrieval quality is where most systems fail.** You can have a great LLM but if retrieval is bad, the system is bad.

**Critical for:** RAG systems, AI infrastructure, search optimization, data science roles.

**Core insight:** BM25 alone is slow and misses semantic nuances. Vector search alone is brittle and doesn't handle exact keywords. You need hybrid (dense + sparse) + reranking + evals to get it right.

---

## First Principle: Retrieval Quality Problem

Imagine a chatbot that answers questions about AWS:

```
User: "How do I set up a VPC?"

Ideal retrieval:
  1. AWS VPC setup guide (exact, relevant)
  2. VPC best practices (context)
  3. VPC security groups (related)
  
Bad retrieval (dense embeddings only):
  1. AWS EC2 scaling (similar vector distance, wrong topic)
  2. VPC networking basics (okay, but not setup-focused)
  3. Lambda VPC configuration (tangential)
  
User question: "VPC setup"
Embedding: "What word vectors are most similar to 'VPC setup'?"
Vector DB might match: "instance setup", "container setup" (similar words)
Precision: 30% (3 out of 10 results are actually about VPC)
```

**Why this happens:**
- Dense embeddings capture semantic similarity
- But they miss exact phrase matching (keyword importance)
- "VPC setup guide" vs. "instance setup guide" are similar in embedding space
- Ranking purely by vector similarity loses important signals

---

## Solution 1: Hybrid Search (Dense + Sparse)

Combine vector search with traditional keyword search (BM25):

```
User query: "VPC setup guide"

Sparse search (BM25):
  Matches documents with keywords: "VPC", "setup", "guide"
  Scoring: TF-IDF (term frequency, inverse document frequency)
  
  Results:
  1. AWS VPC setup guide (score: 8.5) ✓
  2. VPC security setup (score: 7.2) ✓
  3. EC2 setup in VPC (score: 6.5) ✓

Dense search (vector embeddings):
  Encodes query to embedding
  Finds nearest neighbors in vector space
  
  Results:
  1. EC2 scaling (score: 0.92) ✗
  2. Container networking (score: 0.90) ✗
  3. VPC best practices (score: 0.88) ✓

Hybrid combination:
  Merge both results (normalized scores)
  Weight: 60% sparse + 40% dense
  
  Final ranking:
  1. AWS VPC setup guide (0.6 * 8.5 + 0.4 * 0.2) = 5.3
  2. VPC security setup (0.6 * 7.2 + 0.4 * 0.3) = 4.5
  3. VPC best practices (0.6 * 5.0 + 0.4 * 0.88) = 3.5
```

**Implementation:**

```python
from elasticsearch import Elasticsearch
from pinecone import Index
import numpy as np

class HybridRetriever:
  def __init__(self, bm25_client: Elasticsearch, vector_db: Index):
    self.bm25 = bm25_client
    self.vectors = vector_db
  
  def search_hybrid(self, query: str, top_k: int = 10):
    # BM25 search
    bm25_results = self.bm25.search(
      index="documents",
      body={
        "query": {"multi_match": {"query": query, "fields": ["title", "content"]}}
      },
      size=top_k
    )
    
    # Vector search
    query_embedding = encode(query)  # Get embedding
    vector_results = self.vectors.query(
      vector=query_embedding,
      top_k=top_k
    )
    
    # Normalize scores (both to [0, 1])
    bm25_scores = {r['_id']: r['_score'] for r in bm25_results['hits']['hits']}
    max_bm25 = max(bm25_scores.values()) if bm25_scores else 1
    bm25_normalized = {k: v / max_bm25 for k, v in bm25_scores.items()}
    
    vector_scores = {r['id']: r['score'] for r in vector_results}
    vector_normalized = vector_scores  # Already 0-1
    
    # Merge with weights
    combined = {}
    for doc_id in set(bm25_normalized.keys()) | set(vector_normalized.keys()):
      bm25_score = bm25_normalized.get(doc_id, 0)
      vector_score = vector_normalized.get(doc_id, 0)
      combined[doc_id] = 0.6 * bm25_score + 0.4 * vector_score
    
    # Sort and return
    sorted_results = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return [(doc_id, score) for doc_id, score in sorted_results[:top_k]]
```

**When to use hybrid:**
- Exact phrase matching matters (customer support, FAQ)
- Domain-specific terminology (medical, legal documents)
- Performance-critical (hybrid faster than ensemble of multiple retrievers)

---

## Solution 2: Reranking (Post-Retrieval Scoring)

Retrieve top 100 documents with dense search, then rerank with a more sophisticated model:

```
Initial retrieval (fast, vector embeddings):
  Query: "VPC setup"
  Returns: Top 100 documents (could include noise)
  
Reranking (slow, but accurate):
  Use cross-encoder: RoBERTa-based model optimized for ranking
  Score each of top 100: P(query_relevant|document)
  
  Example scores:
  1. AWS VPC setup guide: 0.98 (highly relevant)
  2. VPC security setup: 0.85
  3. EC2 setup in VPC: 0.72
  4. Container networking: 0.15 (low, probably noise)
  
Final ranking:
  Return top 10 by reranker score
```

**Implementation:**

```python
from sentence_transformers import CrossEncoder

class RerankingRetriever:
  def __init__(self, initial_retriever, reranker_model="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"):
    self.retriever = initial_retriever
    self.reranker = CrossEncoder(reranker_model)
  
  def search_with_reranking(self, query: str, initial_top_k: int = 100, final_top_k: int = 10):
    # Initial retrieval (cheap)
    candidates = self.retriever.search(query, top_k=initial_top_k)
    
    # Rerank (expensive, but only on top_k)
    queries = [query] * len(candidates)
    docs = [doc['content'] for doc in candidates]
    
    reranker_scores = self.reranker.predict(list(zip(queries, docs)))
    
    # Sort by reranker score
    ranked = sorted(
      zip(candidates, reranker_scores),
      key=lambda x: x[1],
      reverse=True
    )
    
    return [doc for doc, score in ranked[:final_top_k]]
```

**Cost/benefit:**
```
Retrieval alone:
  Latency: 10-50ms (vector DB fast)
  Accuracy: 70% (vector search has false positives)
  Cost: $0.01 per query (vector DB cheap)

Reranking (on top 100):
  Latency: 500ms (cross-encoder inference)
  Accuracy: 90% (reranker filters noise)
  Cost: $0.05 per query (reranking service)

Reranking (on top 10):
  Latency: 50ms (only 10 documents)
  Accuracy: 95% (reranked, fewer docs)
  Cost: $0.005 per query (minimal)
```

**Tradeoff:** Reranking on top 10 (after initial retrieval) is best: fast enough, accurate, cost-effective.

---

## Solution 3: Retrieval Evaluation Metrics

How do you know if your retrieval is good?

### Metric 1: Mean Reciprocal Rank (MRR)

Position of first correct answer:

```
Query: "How to set up VPC?"

Retrieval results:
1. EC2 setup (not VPC) ✗
2. VPC security (related, not setup guide) ✗
3. AWS VPC setup guide (CORRECT) ✓
4. VPC best practices

MRR = 1 / rank_of_first_correct = 1 / 3 = 0.33

Interpretation:
  MRR = 1.0: First result is correct (perfect)
  MRR = 0.5: Correct answer at position 2 (good)
  MRR = 0.33: Correct answer at position 3 (okay)
  MRR = 0.0: No correct answer in top 10 (bad)
```

**When to use:** Single-answer questions (search, FAQ, customer support).

### Metric 2: Normalized Discounted Cumulative Gain (NDCG)

Accounts for ranking and relevance grades:

```
Query: "VPC setup"
Ground truth: Which docs are relevant?
  AWS VPC setup guide: Highly relevant (grade 2)
  VPC best practices: Somewhat relevant (grade 1)
  VPC security: Somewhat relevant (grade 1)
  EC2 setup: Not relevant (grade 0)

Retrieval results (in order):
1. EC2 setup (grade 0)
2. AWS VPC setup guide (grade 2)
3. VPC best practices (grade 1)
4. VPC security (grade 1)

DCG = rel_1 / log2(1+1) + rel_2 / log2(2+1) + rel_3 / log2(3+1) + rel_4 / log2(4+1)
    = 0 / 1 + 2 / 1.58 + 1 / 2 + 1 / 2.32
    = 0 + 1.26 + 0.5 + 0.43
    = 2.19

IDCG (ideal ranking):
1. AWS VPC setup guide (grade 2)
2. VPC best practices (grade 1)
3. VPC security (grade 1)
4. EC2 setup (grade 0)

IDCG = 2 / 1 + 1 / 1.58 + 1 / 2 + 0 / 2.32
     = 2 + 0.63 + 0.5 + 0
     = 3.13

NDCG = DCG / IDCG = 2.19 / 3.13 = 0.70

Interpretation:
  NDCG = 1.0: Perfect ranking
  NDCG = 0.7: Pretty good
  NDCG = 0.5: Okay
  NDCG < 0.3: Bad
```

**When to use:** Multi-answer questions, ranking tasks (where relevance grades matter).

### Metric 3: Mean Average Precision (MAP)

Relevant docs should be ranked early:

```
Query: "VPC setup"
Ground truth: Document IDs that are relevant: [1, 3, 5, 7]

Retrieval results:
1. Doc 1 (relevant) ✓ → Precision@1 = 1/1 = 1.0
2. Doc 2 (not relevant) ✗
3. Doc 3 (relevant) ✓ → Precision@3 = 2/3 = 0.67
4. Doc 4 (not relevant) ✗
5. Doc 5 (relevant) ✓ → Precision@5 = 3/5 = 0.6
6. Doc 6 (not relevant) ✗
7. Doc 7 (relevant) ✓ → Precision@7 = 4/7 = 0.57
8. Doc 8 (not relevant) ✗

AP = (1.0 + 0.67 + 0.6 + 0.57) / 4 = 0.71

Interpretation:
  AP = 1.0: All relevant docs ranked first (perfect)
  AP = 0.7: Pretty good
  AP = 0.5: Okay
```

**When to use:** Multi-answer queries where you want all relevant docs ranked high.

---

## Building a Retrieval Eval Suite

```
Test set: 100 queries with ground truth annotations

For each query:
  - Query text
  - Relevant document IDs (human-annotated)
  - Irrelevant document IDs
  - Relevance grades (if using NDCG)

Evaluation:
  1. Run retrieval on all 100 queries
  2. Compute MRR@10, NDCG@10, MAP@10 for each query
  3. Aggregate: MRR_avg = mean(MRR across all queries)
  
Results:
  MRR@10: 0.75 (first relevant doc at position ~1.5 on average)
  NDCG@10: 0.72 (ranking quality)
  MAP@10: 0.68 (precision of relevant docs)

Interpretation:
  These are strong baseline metrics for a retrieval system.
  Typical benchmarks:
    NDCG@10 > 0.60 = good
    NDCG@10 > 0.75 = excellent
```

---

## Quality Gates: When to Update Retrieval

```
Monitoring in production:

User feedback (implicit):
  - Did user click the retrieved result? (positive signal)
  - Did user reformulate query? (negative signal)
  - Did user search again? (negative signal)

Metrics:
  - Click-through rate (CTR): % of retrievals that user clicked
  - Dwell time: How long user spent on retrieved page
  - Query reformulation rate: % that lead to follow-up searches

Quality gate:
  If CTR < 0.30:  Alert: retrieval quality may be degrading
  If CTR < 0.20:  Action: Debug and improve retrieval
  
  Trigger reranking if:
    - NDCG@10 drops below 0.65
    - MRR@10 drops below 0.70
```

---

## Interview Q&A

**Recall 1:** What's the difference between sparse (BM25) and dense (embeddings) search?

*Must-say:*
- **Sparse (BM25):** Keyword-based, TF-IDF scoring. Fast, exact phrase matching.
- **Dense (embeddings):** Vector similarity. Slower, captures semantic meaning.
- **Hybrid:** Combine both for best accuracy and speed.

**Probe 1:** You built a RAG system. Retrieval is 90% accurate (NDCG = 0.90). LLM is 85% accurate. Overall system is?

*Expected:*
- Overall ≤ 90% * 85% = 76.5% (system is bottlenecked by retrieval)
- If you improve retrieval to 95%, overall becomes 95% * 85% = 80.75% (significant gain)
- Retrieval is often the bigger lever; don't just focus on LLM.

**Probe 2:** Retrieval latency is 50ms (vector search). Reranking adds 500ms. Worth it?

*Expected:*
- Depends on use case.
- If search latency budget is 100ms: No, reranking breaks SLA.
- If latency budget is 1s: Yes, worth it (quality gain).
- If reranking can be async (background): Yes, always good.
- Alternative: Rerank only top 10 (faster, ~50ms).

**Numeric 1:** You have 1000 queries with ground truth labels. You run retrieval and get MRR = [1.0, 0.5, 0.33, 1.0, ...] (one MRR per query). Average is?

*Working:*
- MRR_avg = sum(all MRR scores) / num_queries
- If 80% have MRR = 1.0 and 20% have MRR = 0.5
- Average: 0.8 * 1.0 + 0.2 * 0.5 = 0.8 + 0.1 = 0.9
- Interpretation: Strong retrieval (first result correct 90% of the time)

**Numeric 2:** You rerank top 100 results with a cross-encoder that takes 5ms per document. Latency?

*Working:*
- Reranking time: 100 documents * 5ms = 500ms
- If initial retrieval was 30ms: Total = 30 + 500 = 530ms
- If you rerank only top 10: 10 * 5 = 50ms, total = 80ms
- Answer: ~500ms (or ~50ms if optimized)

---

## Checklist: Production Retrieval Quality

- [ ] **Implement hybrid search (BM25 + vectors).** Not just embeddings.
- [ ] **Use reranking on top-k results.** Cross-encoder for ranking.
- [ ] **Define eval metrics (NDCG, MRR, MAP).** Can't improve what you don't measure.
- [ ] **Build eval set with ground truth.** 100+ queries with human-annotated answers.
- [ ] **Monitor retrieval quality in production.** CTR, dwell time, user feedback.
- [ ] **Set quality gates and alerts.** Trigger action if NDCG < 0.65.
- [ ] **A/B test retrieval improvements.** Measure impact on end-to-end system.
- [ ] **Profile retrieval latency.** Optimize bottleneck (vector DB, reranking, etc.).

### Common Wrong Answers

- "I'll just use vector search, it's state-of-the-art." ← Missing keyword matching, will fail on domain terminology.
- "Reranking is too slow, skip it." ← Can be optimized (top-k only, async); worth the quality gain.
- "NDCG = 1.0 means perfect retrieval." ← No, means perfect ranking; doesn't guarantee user satisfaction.
- "I don't need to evaluate retrieval, LLM will handle bad results." ← No, garbage in = garbage out.

---

## Story Card: Customer Support RAG Failure

**Context:** SaaS company builds customer support chatbot with RAG. Knowledge base: 10,000 help articles.

**Initial system (dense search only):**
```
Customer: "How do I enable 2FA?"

Retrieval returns:
1. "How to reset password" (similar vectors)
2. "Account security best practices" (similar vectors)
3. "Enable 2FA" (correct answer, but ranked #8)

Chatbot: "Here's info on password reset..."
Customer: "That's not what I asked!"

NDCG@10: 0.45 (poor)
User satisfaction: 35%
```

**Problem analysis:**
- Vector search captures "security" / "account" but misses exact keywords "2FA"
- BM25 would have ranked "Enable 2FA" first (exact phrase match)

**Fix: Hybrid search + reranking**
```
Hybrid search:
  - BM25 (keyword): "Enable 2FA" gets high score (keywords match)
  - Vectors: Related articles also scored
  - Combine: "Enable 2FA" ranks first

Reranking (optional):
  - Cross-encoder scores each result
  - Confirms "Enable 2FA" is most relevant
  
Result:
  1. "Enable 2FA" (correct)
  2. "Two-factor authentication setup" (related)
  3. "Account security" (context)

NDCG@10: 0.92 (excellent)
User satisfaction: 85%
```

**Lesson:** Hybrid search is table-stakes for production RAG. Vector search alone is not enough.

---

## Further Study

- **BM25 and TF-IDF:** Classic information retrieval fundamentals
- **ColBERT / ANCE:** Dense retrieval architectures
- **Cross-encoder ranking:** Sentence Transformers documentation
- **BEIR benchmark:** Standard retrieval evaluation benchmark
- **Elasticsearch + Vector DB:** Practical hybrid implementation
