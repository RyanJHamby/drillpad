# Back-of-Envelope Estimation

## Why It Matters

"Design a system for YouTube." You have 45 minutes. You can't actually code it. But you can estimate: "1B users, 1M uploaders/day, 5PB storage/year, 100K servers."

These numbers are **your foundation**. They guide every decision: database size (sharding?), throughput (threads?), latency (caching layer?), cost.

---

## Core Numbers to Memorize

```
Time:
  1 sec = 1,000 ms = 1,000,000 µs
  1 min = 60 sec
  1 hour = 3,600 sec
  1 day = 86,400 sec
  1 year ≈ 31M sec = 365 days

Latency (empirical):
  L1 cache: 4 ns
  L2 cache: 10 ns
  L3 cache: 40 ns
  RAM: 100 ns
  SSD random read: 1 ms
  HDD random read: 10 ms
  Network RTT (local): 1 ms
  Network RTT (cross-country): 50 ms
  Database query: 5-10 ms
  
Storage:
  1 KB = 1,000 bytes
  1 MB = 1,000 KB
  1 GB = 1,000 MB
  1 TB = 1,000 GB
  1 PB = 1,000 TB
  
  RAM cost: $10/GB
  SSD cost: $0.10/GB
  HDD cost: $0.02/GB
  Network: $0.10/GB
  
Bandwidth:
  1 Mbps = 125 KB/s
  10 Mbps = 1.25 MB/s
  100 Mbps = 12.5 MB/s
  1 Gbps = 125 MB/s
  
QPS (single server):
  Redis: 100K QPS
  Postgres: 1K-10K QPS (depends on query)
  Elasticsearch: 10K QPS
  Memcached: 100K QPS
```

---

## Estimation Framework

### Step 1: User Scale

```
Example: Design a messaging app

1. DAU (daily active users)
   - Competitors: WhatsApp 100M DAU, Slack 10M DAU
   - Estimate: 50M DAU (WhatsApp scale but smaller)

2. QPS (messages sent)
   - Messages per user per day: 10 (average)
   - QPS = DAU * messages/day / 86,400
   - = 50M * 10 / 86,400 = 5,787 QPS
   - Peak (5x): 29,000 QPS
   
3. Storage
   - Messages per day: 50M * 10 = 500M
   - Message size: 200 bytes (with metadata)
   - Per day: 500M * 200 = 100 GB/day
   - Per year: 100 GB * 365 = 36.5 TB/year
   - Retention: 2 years = 73 TB
```

### Step 2: Throughput & Latency

```
Scenario: API endpoint /send_message

Throughput (QPS):
  ├─ Peak: 29K QPS (from above)
  ├─ Server capacity: 100 QPS/server (includes I/O, serialization)
  ├─ Servers needed: 29K / 100 = 290 servers
  └─ With redundancy (3x): 290 * 3 = 870 servers (high!)
  
  Optimization: cache, batching
    └─ Could reduce to 30-50 servers with optimization

Latency (P99 target: 100 ms):
  
  [Client] ---(50ms)---> [LoadBalancer]
  [LB] ---(1ms)---> [API Server]
  [Server] ---(5ms)---> [Database write]
  [Server] ---(1ms)---> [Emit to queue]
  [Server] ---(1ms)---> [Response]
  Total: 58 ms (under budget)
```

### Step 3: Data Storage

```
Database design:

PK: (sender_id, timestamp)  [because conversations are time-series]
Total: 73 TB

Partition:
  - By sender: 50M users
  - Per partition: 73 TB / 50M = 1.5 MB per user (fits in RAM)
  - Shards: 1000 shards, each 73 GB

Replication:
  - RF = 3 (3 copies)
  - Total: 73 TB * 3 = 219 TB (cluster size)

Cost:
  - SSD: 219 TB * $0.10/GB = $21.9M (one-time)
  - Annual: $21.9M / 5 years = $4.4M/year
  - Monthly: $366K/month
```

---

## Common Estimation Patterns

### User Growth

```
Initial: 1M users
Growth: 20% month-over-month
After N months: 1M * (1.2)^N

Month 12: 1M * (1.2)^12 ≈ 9M users
Month 24: 1M * (1.2)^24 ≈ 80M users

Design for: max 24-month projection
```

### Pareto Distribution (80-20 Rule)

```
Users: 100M total
Activity:
  - Top 1% (1M users) generate 80% of load
  - Bottom 99% generate 20% of load

Implication:
  - Can't average users
  - Need to handle hot users (large fan-out, many followers)
  - Cache hot users aggressively
```

### Bandwidth Bottleneck

```
System: photo sharing (Instagram scale)

Photos:
  - 100M DAU
  - 1 photo per user per day
  - Photo size: 2 MB

Bandwidth:
  - Per day: 100M * 2 MB = 200 TB/day
  - Per second: 200 TB / 86,400 sec = 2.3 TB/sec
  - In Gbps: 2.3 TB/sec * 8 Gbps/TB = 18 Tbps
  - (Exabytes scale, massive!)
  
Optimization:
  - Compression: JPEG ~70% reduction → 1.4 TB/sec
  - CDN: cache at edge → 1.4 TB origin bandwidth
  - Caching: 90% cache hit → 140 Gbps needed
  
Cost:
  - 1.4 TB/day * $0.10/GB = $140/day = $51K/year (reasonable)
```

---

## Worked Example: Video Streaming Service

```
Goal: Design service like YouTube

Scale:
  - 2B users (world population × 28%)
  - 300M DAU
  - Uploads: 500 hours/min (observed YouTube)
  - Playback: ?
  
Estimate playback:
  ├─ DAU: 300M
  ├─ Video views/user/day: 5 (average)
  ├─ Total views: 1.5B views/day
  ├─ QPS: 1.5B / 86,400 = 17,361 QPS
  ├─ Peak (10x, primetime): 173,610 QPS
  
Storage (uploads):
  ├─ 500 hours/min = 43.2M hours/day
  ├─ File size: 1 GB/hour (MP4, HD)
  ├─ Per day: 43.2 PB/day
  ├─ Per year: 43.2 PB * 365 = 15.8 EB/year
  ├─ Retention: 10 years = 158 EB
  └─ Cost: 158 EB * $0.02/GB = $3.2 billion (expensive!)
  
Optimization:
  ├─ Old videos (>1 year): compress 50% → saves $1.6B
  ├─ Delete unpopular (< 10 views): another 30% → saves $500M
  ├─ Clever encoding: further compression
  └─ Final cost: ~$1B/year (YouTube scale)

Servers (origin):
  ├─ QPS: 173K
  ├─ Per server: 100 QPS
  ├─ Servers: 1,730
  ├─ Redundancy: 3x → 5,190 servers
  ├─ Cost: 5,190 * $1/hour * 730 hours/month = $3.8M/month
  
CDN (edge):
  ├─ 90% of traffic from cache (not origin)
  ├─ QPS to origin: 17,361 (not 173K)
  ├─ Servers: 173
  ├─ CDN cost: 43.2 PB/day * $0.10/GB = $4.3M/day = $130M/month
  └─ Way cheaper than building own CDN globally
```

---

## Interview Tips

**Do's:**
- Write out the math (show your thinking)
- State assumptions (DAU, growth rate, retention)
- Use round numbers (1M not 1.237M)
- Sanity check (result reasonable?)
- Update estimates (if challenged)

**Don'ts:**
- Overthink precision (1.9B vs 2B matters less than order of magnitude)
- Forget to account for growth/retention
- Ignore cost (interviewer cares about infrastructure cost)
- Make up numbers (estimate based on known services)

**Sanity Checks:**
```
1B users × 100 bytes/user = 100 GB ✓ (fits on one node)
1B users × 1 MB/user = 1 PB ✓ (needs sharding)
1M QPS × 100 bytes/message = 100 Mbps ✓ (fits on one link)
1M QPS × 100 KB/message = 100 Gbps ✗ (needs massive bandwidth)
```

---

## Common Wrong Answers

- ❌ "I don't know, it depends" — always make an estimate
- ❌ "Just use one database" — if >1TB total, need partitioning
- ❌ "Ignore storage cost" — can be 50% of total budget
- ❌ "Assume no peak traffic" — peak = 5-10x average (critical!)
- ❌ "Round numbers = bad" — actually round numbers are good (easier math)
