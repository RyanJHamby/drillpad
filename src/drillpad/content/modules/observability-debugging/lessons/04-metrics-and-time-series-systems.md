# Metrics & Time-Series Systems (Prometheus / Datadog)

## Problem

1B metrics/sec. 30-day retention. Query: "CPU > 90% for 5+ min". <100ms latency.

## Architecture

```
Metrics ingestion:

  App: emit metric
    ├─ timestamp: 1609459200000
    ├─ name: "http_request_latency"
    ├─ labels: {method: "GET", endpoint: "/api/users", status: "200"}
    ├─ value: 45.3 (ms)
    └─ Emit: UDP or HTTP to collector

  Collector (Prometheus-style):
    ├─ Scrape endpoints every 15 sec
    ├─ Parse metrics
    ├─ Buffer in memory: 1 min of metrics
    └─ Write to time-series database

  Time-series database (TSDB):
    ├─ Ingest rate: 1B metrics/sec
    ├─ Compression: compress values, drop duplicates
    ├─ Storage: column-oriented (good for time-series)
    ├─ Partitioning: by day or hour (fast pruning old data)
    └─ Retention: 30 days
    
  Query engine:
    ├─ PromQL: SELECT avg(cpu_usage) WHERE time > now() - 1h
    ├─ Aggregation: sum, avg, max, percentile
    ├─ Alerts: trigger when condition met
```

## Time-Series Compression

```
Raw data (uncompressed):
  ├─ Timestamp: 8 bytes
  ├─ Value: 8 bytes (float64)
  ├─ Labels: 200 bytes avg
  └─ Total: 216 bytes per metric

1B metrics/sec = 216 GB/sec (uncompressed!)

Compression techniques:

1. Delta-of-delta (timestamps):
   ├─ Metric 1: timestamp 1000, delta = 1000
   ├─ Metric 2: timestamp 1015, delta = 15, delta-of-delta = 15 - 1000 = -985
   ├─ Metric 3: timestamp 1030, delta = 15, delta-of-delta = 0
   └─ Encode delta-of-delta as varint (often 1 byte!)
   
   Result: timestamps 8 bytes → 1-2 bytes each

2. XOR for floats:
   ├─ Store XOR of consecutive values
   ├─ Often zeros in MSBs (similar readings)
   ├─ Varint encoding: 1-2 bytes instead of 8

3. Label pooling:
   ├─ Unique labels: {method, status, endpoint} = 1000 unique combos
   ├─ Store each once, reference by ID
   ├─ Metric: [id=45, value] instead of [labels, value]

Result:
  ├─ Raw: 216 bytes
  ├─ Compressed: 10-20 bytes (10-20x compression!)
  ├─ At 1B metrics/sec: 10-20 GB/sec → manageable

Storage per day:
  ├─ 1B metrics/sec * 86,400 sec = 86.4B metrics/day
  ├─ At 15 bytes/metric: 1.3 TB/day
  ├─ 30 days: 39 TB
```

## Partitioning & Retention

```
Partition by time:

  Day 0 (2025-01-01): day_0.db (1.3 TB)
  Day 1 (2025-01-02): day_1.db (1.3 TB)
  ...
  Day 29 (2025-01-30): day_29.db (1.3 TB)
  Day 30 (2025-01-31): day_30.db (1.3 TB) → delete today

Benefits:
  ├─ Query "last 7 days": read day_24-30 only (9.1 TB, not 39 TB)
  ├─ Delete old data: drop day_0 entirely (no compaction)
  ├─ Parallelism: read different days in parallel

Shard by metric:

  Metric 1 (http_latency): node_0
  Metric 2 (cpu_usage): node_1
  ...
  Metric N: node_k
  
  Parallel ingestion: N collectors → N nodes
  No contention: each node handles disjoint metrics
```

## Query Examples

```
Prometheus QL:

# Average latency over last hour
avg(http_request_latency{endpoint="/api/users"})

# 99th percentile (P99)
histogram_quantile(0.99, rate(http_request_latency[5m]))

# Rate of requests per second
rate(http_requests_total[1m])

# Alerting rule
ALERT HighCPU
  IF avg(cpu_usage) > 90
  FOR 5m
  THEN send_alert()

Complexity:
  ├─ Parse: O(1)
  ├─ Retrieve: O(log n) [B-tree index]
  ├─ Aggregate: O(n)
  ├─ Total: O(n) where n = metrics in time range
```

## Cardinality Explosion

```
Problem: unlimited labels cause explosion

Bad:
  http_request_latency{method, endpoint, user_id, ...}
  
  Unique combinations:
    ├─ 10 methods
    ├─ 1000 endpoints
    ├─ 1M users
    └─ Total: 10B unique metric series!
  
  Cost: 10B series * 15 bytes = 150 TB (way over budget)

Solution: limit cardinality

  Good:
    http_request_latency{method, endpoint, status}
    ├─ 10 methods
    ├─ 1000 endpoints
    ├─ 10 statuses
    └─ Total: 100K series (manageable)
  
  User_id NOT a label (too high cardinality)
  → Instead: store in separate application log

Rule:
  ├─ Cardinality = product of unique label values
  ├─ Keep < 1M series per metric
  └─ Validate: metrics scrape latency increasing? → cardinality explosion
```

## Failure Modes

```
Collector crashes:
  ├─ App continues to emit metrics (buffered locally, or lost)
  ├─ Recovery: start new collector, scrape endpoint again
  ├─ Data loss: last few minutes

TSDB full:
  ├─ Retention exceeded before cleanup
  ├─ Cause: ingest rate > expected
  ├─ Solution: auto-delete oldest data, alert ops

Cardinality explosion:
  ├─ New label added: user_id
  ├─ Series multiply: 100K → 100B
  ├─ TSDB OOM (out of memory)
  └─ Prevention: validate schema changes
```

---

## Interview Checklist

- [ ] Delta-of-delta compression for timestamps
- [ ] XOR compression for floats
- [ ] Partitioning by time for retention
- [ ] Cardinality control (label limits)
- [ ] Scale: 1B metrics/sec, 30-day retention, 39 TB
- [ ] Query: PromQL, aggregations, alerting
- [ ] Indexes: efficient time-range queries

## Common Wrong Answers

- ❌ "Store raw metrics" — 216 TB/day, unsustainable
- ❌ "Add all labels" — cardinality explosion
- ❌ "Keep all data forever" — storage grows unbounded
- ❌ "No compression" — compress to 10-20 bytes/metric needed
