# System Design: Search & Log Indexing

## Firm Archetype: Elastic, Google, AWS, Datadog

**Problem:** Index 1B documents, search in 100ms. Real-time updates.

**Why hard:** Indexing latency vs search speed, scale to 1B docs.

---

## Architecture

```
Documents flow:
  Kafka (1000 docs/sec) → Indexer → Elasticsearch cluster

Search flow:
  Query API → Elasticsearch → Results

Elasticsearch cluster:
  ├─ 10 data nodes (hold index shards)
  ├─ 3 master nodes (coordinate)
  └─ 3 coordinating nodes (route searches)

Index structure:
  ├─ 100 shards (distribute docs across nodes)
  │  └─ Each shard: inverted index (word → doc IDs)
  ├─ 2 replicas (fault tolerance)
  └─ Total: 300 shards (100 * 3 replicas)
```

---

## Key Tradeoffs

**1. Indexing latency vs search speed**
- Real-time (1ms) index: search slow
- Batch index (5 min): search fast
- Decision: refresh every 1 second (1s index latency, < 100ms search)

**2. Index size**
- Uncompressed: 1B docs * 1KB = 1TB
- Compressed (Elasticsearch default): ~100GB
- Tradeoff: compression cost (5% slower search, 10x smaller size)
- Decision: compress (storage is cheaper than hardware)

**3. Sharding strategy**
- Shard by timestamp (logs): newer docs in faster shards
- Shard by hash(doc_id): even distribution
- Decision: by timestamp (most searches are recent, faster)

---

## Scaling Calculation

```
1B documents, 1KB average
Total size: 1TB (uncompressed), 100GB (compressed)

Elasticsearch:
  Per node: 100GB (we have 10 nodes = 1TB capacity)
  With 2 replicas: need 30 nodes total (10 data + 20 replicas)
  
Search QPS:
  10K searches/sec peak
  Per shard: 10K / 100 shards = 100 QPS
  P99 search latency: 50ms (per shard)
  With routing: 100ms (network + aggregation)
```

---

## Indexing Pipeline

```python
class SearchIndexer:
    def __init__(self):
        self.kafka = KafkaConsumer('documents')
        self.es = ElasticsearchClient()
        self.batch_size = 1000
    
    def index_documents(self):
        """Batch index documents."""
        batch = []
        for doc in self.kafka:
            batch.append(doc)
            if len(batch) >= self.batch_size:
                self.es.bulk_index(batch)
                batch = []
        if batch:
            self.es.bulk_index(batch)
    
    def bulk_index(self, docs):
        """Send batch to Elasticsearch."""
        # Bulk API: 1000 docs in one request
        # Latency: 100ms for 1000 docs (0.1ms per doc)
        # vs 1ms per doc if single-document indexing
        self.es.bulk(docs)
```

---

## Search Query Optimization

```
Query: "find logs with error=503 in last hour"

Slow approach:
  Scan all 1B docs
  Filter by error code
  Filter by timestamp
  Time: 30 seconds (unacceptable)

Fast approach (with indexing):
  1. Filter by timestamp (shard selection)
     → Only search last hour's shards (3 shards instead of 100)
  
  2. Inverted index lookup (error=503)
     → Direct lookup, not scan
     → 10ms (index lookup)
  
  3. Fetch and rank results
     → Return top 10
  
  Total: 100ms (acceptable)
```

---

## Failure Handling

```
Elasticsearch node fails:
  → Replica shard promoted to primary
  → No data loss (replicas have copy)
  → Search continues (queries routed to healthy nodes)
  
Indexing slow:
  → Kafka backlog grows
  → Add more indexer processes (auto-scale)
  → Or: reduce refresh rate (1s → 5s, live with stale)
  
Search latency spike:
  → Might be GC (pause all shards)
  → Or: too much aggregation (too many results)
  → Add more coordinating nodes (route queries faster)
```

---

## Q&A

**Recall 1:** Why batch indexing instead of one doc at a time?

*Must-say:*
- Single: 1ms per doc
- Batch (1000): 100ms for 1000 = 0.1ms per doc
- 10x faster
- Tradeoff: 100ms latency per batch (acceptable)

**Probe 1:** Indexing falls behind (Kafka lag grows). What do you do?

*Expected:*
- Add more indexer processes (scale horizontally)
- Or: temporarily reduce refresh rate (1s → 5s)
- Or: reduce batch size (let docs into search sooner)

**Numeric 1:** 1B docs, 100 shards, 2 replicas. Per-shard doc count?

*Working:*
- 1B docs / 100 shards = 10M docs per shard
- With 2 replicas: 3 copies per shard
- Total docs stored: 1B * 3 = 3B doc copies
- Storage: 3B * 1KB = 3TB (uncompressed)

