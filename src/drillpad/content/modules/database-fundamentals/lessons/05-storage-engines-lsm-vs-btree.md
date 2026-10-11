# Storage Engines: LSM Trees vs B-Trees — Write Amplification & Space Trade-Offs

## Overview

The choice between LSM (Log-Structured Merge) trees and B-trees determines your database's read/write latency, space efficiency, and compaction overhead. This lesson covers:

1. Why LSM trees are write-optimized (but read-pessimized)
2. Why B-trees are read-optimized (but write-pessimized)
3. Write amplification, read amplification, space amplification
4. Compaction strategies and their costs
5. When to use each (RocksDB vs PostgreSQL vs Cassandra)

---

## The Problem: Read vs Write Optimization

**Scenario:** Building a time-series database for trading (1M inserts/sec, 10K reads/sec).

```
Naive approach: Single sorted file on disk

Write path:
  1. Append new record to file
  2. Write to disk (sequential write = fast)
  3. Cost per write: 1 disk operation

Read path:
  1. Binary search in file
  2. But file grows to 100GB
  3. Cost per read: log2(100GB) = 37 disk seeks (~180ms)
  
Problem: Reads are 10,000x slower than acceptable
```

**The fundamental trade-off:**
- **Write-optimized:** Fast inserts, slow reads (LSM)
- **Read-optimized:** Slow inserts, fast reads (B-tree)

---

## B-Trees: The Read-Optimized Standard

B-trees (used in PostgreSQL, MySQL InnoDB, SQLite) keep data in a sorted tree structure.

```
Insert: user_id=50 into B-tree

      [30|60]
      /  |  \
    [10][40][70]

Step 1: Find leaf containing 50 (between 40 and 70)
  → Lookup chain: root → [60] → [70] branch
  → Cost: 3 disk seeks, 3 * 5ms = 15ms

Step 2: Insert 50 into leaf
  Leaf is full: [30, 40, 70, 90]
  Split: promotes 70 up
  
Result: 40-50ms per write (3-4 seeks)
```

**Read path (fast):**

```
Query: Find user_id=50

      [30|60]
      /  |  \
    [10][40][70]

Lookup: root → [30|60] → [40] → 50 ✓
Cost: 3 disk seeks = 15ms
```

**Problem: Write amplification during splits**

When a B-tree node splits, you rewrite multiple levels:

```
Insert 100 times into 100-node B-tree:
  100 inserts × 3 seeks each = 300 disk operations
  But also: nodes rebalance, parent splits cascade up
  Actual: ~400-500 disk operations (write amplification ≈ 5x)
  
Sequential inserts in B-tree: worst case
  Every leaf fills up → splits → parent fills → splits up
  Write amplification can reach 10x
```

**B-tree write amplification formula:**

```
Write-amp = (1 + height of tree) * (rewrite on split)
           ≈ (1 + log(N)) * 2
           
For 1M records: (1 + log(1M)) × 2 ≈ (1 + 20) × 2 = 42x
  → 1 logical write = 42 physical disk writes
```

---

## LSM Trees: The Write-Optimized Standard

LSM (Log-Structured Merge) trees (used in RocksDB, Cassandra, HBase) buffer writes in memory, then flush to disk sequentially.

```
Write path:

Time 1: Write user_id=50 to in-memory buffer (memtable)
  → Cost: ~100 nanoseconds (memory write)

Time 2: Memtable fills (e.g., 64MB)
  → Flush to disk as "SSTable" (sorted string table)
  → Cost: sequential disk write = fast (~500ms for 64MB)
  
Time 3: Write user_id=100 to new memtable
  → Cost: ~100 nanoseconds (no blocking)

Result: Amortized cost per write ≈ 500ms / 1M writes = 0.5 µs per write
```

**Read path (slower, but acceptable):**

```
Query: Find user_id=50

Step 1: Check memtable (in-memory)
  → Cache hit (100ns) or miss

Step 2: Check SSTables on disk (binary search each)
  SSTables: SSTable_1, SSTable_2, SSTable_3, ...
  → Need to check each one (or use bloom filter)
  
Cost: 1 memtable check + (number of SSTables) × (log(SSTable size))
  Typical: 1-10 disk seeks = 5-50ms
```

**LSM write amplification:**

```
1M sequential inserts:
  100ns per insert = 100 µs total

When flushing memtable (64MB):
  1 sequential write = 1 disk operation
  
But: Compaction merges SSTables in background
  During compaction: re-read all data, write back (sorted)
  
If compaction reads/writes each key 3x:
  Write-amp = 3x (due to compaction)
  
For time-series (append-only): write-amp ≈ 2-4x
For random updates: write-amp ≈ 5-10x (more compaction)
```

---

## Space Amplification: The Hidden Cost

**B-tree space efficiency:**

```
Data: 1M user records, 1KB each = 1GB total data

B-tree overhead:
  - Tree pointers (each node: ~16 children) = ~5% overhead
  - Unused space in nodes (~30% free for future splits)
  
Space-amp ≈ 1GB + 0.05GB + 0.3GB = 1.35GB
Space factor: 1.35x
```

**LSM space efficiency:**

```
Data: 1M user records, 1KB each = 1GB total data

Memtable:
  - In-memory, not yet written = 0.064GB (one memtable)

SSTables:
  - 1GB on disk (data)
  - Bloom filters: ~10 bits per key = 0.01GB
  - Index blocks: ~100 bytes per key = 0.1GB
  
During compaction:
  - Old SSTables + new SSTables = 2GB temporarily
  
Space-amp ≈ 1GB + 0.11GB (normal) + 1GB (during compaction) = 2.11GB
Space factor: 2.1x (during compaction, can reach 2-3x)
```

**Key difference:** LSM needs 2x space during compaction. B-tree is steady-state.

---

## Compaction Strategies

**LSM compaction algorithm (Leveled, used in RocksDB):**

```
Level 0 (memtables flushed): 4 × 64MB = 256MB
Level 1 (first level):       10 × 64MB = 640MB
Level 2 (second level):      100 × 64MB = 6.4GB
Level 3 (third level):       1000 × 64MB = 64GB

Compaction:
  When Level 1 fills up:
    - Merge all Level 1 files with matching Level 2 files
    - Write new Level 2 files
    - Delete old Level 1 files
    
Cost: Read all Level 1 + read matching Level 2 + write Level 2
  Typical: 10 reads (L1) + 100 reads (L2) + 100 writes = 210 I/O ops
  Per byte: 210 ops / (640MB + 6.4GB) ≈ 0.03 ops/byte = write-amp ≈ 3x
```

**Compaction overhead example:**

```
Scenario: Insert 1TB of data into RocksDB

LSM with leveled compaction:
  Level 0: 256MB × (1TB / 256MB) = 256MB compactions
  Level 1: 640MB × (1TB / 640MB) = 640MB compactions
  Level 2: 6.4GB × (1TB / 6.4GB) = 6.4GB compactions
  Level 3: 64GB × (1TB / 64GB) = 64GB compactions
  
  Total I/O: 1TB × 3 (write-amp) = 3TB of disk I/O
  With 1 TB/s disk bandwidth: 3 seconds of continuous compaction
```

**Alternative: Tiered compaction (Cassandra)**

```
More aggressive merging, fewer levels

Tiered (T=4):
  Level 0: 4 files
  Level 1: 4 files (4^1)
  Level 2: 4 files (4^2)
  
When Level 0 fills: merge into Level 1 (all 4 + 4 new = 8, split into 2 new Level 1)

Compaction cost: lower (fewer levels), but higher space amp (need 2x space per level)
```

---

## Read/Write/Space Amplification Summary

```
                B-Tree    LSM (Leveled)   LSM (Tiered)
Read-amp        1x        3-10x           5-15x
Write-amp       10-100x   2-4x            3-10x
Space-amp       1.1-1.3x  2-3x (comp)     3-5x
Compaction      Background, Explicit merges during      More aggressive
                in-place  LSM level transitions
Latency         ~10-50ms  ~1-100ms        ~1-100ms

Use case:
- B-Tree:      Read-heavy (OLTP), <1M writes/sec
- LSM Level:   Mixed (time-series), 100K-1M writes/sec
- LSM Tier:    Write-heavy (300K+ writes/sec)
```

---

## Real Example: LevelDB (simplified LSM)

```
Insert 10M orders into order book

Write path:
  Order arrives → Append to memtable (in-memory buffer)
  100,000 orders × 100ns = 10ms latency
  
  Memtable fills (64MB): flush to Level 0 SSTable
  Flush time: ~100ms (64MB / 1GB/s bandwidth)
  
  As Level 0 fills (compaction kicks in):
    Compact Level 0 → Level 1
    Read 4 Level 0 files (256MB total)
    Merge with Level 1 files
    Write new Level 1 files
    Background operation, doesn't block writes

Read path:
  Look up order by ID
  1. Check memtable (100ns hit or miss)
  2. Binary search Level 0 SSTable (~5ms, 256MB)
  3. If not found, check Level 1 (slower)
  
  Typical: 1-10ms per read (depends on what level contains key)
  With bloom filters: skip unnecessary levels (~50% faster)
```

**Failure scenario: Compaction can't keep up**

```
Situation: Inserts at 1M/sec, compaction thread is slow (I/O bound)

Time 0: Memtable 1 flushing → Level 0_1
Time 10ms: Memtable 2 flushing → Level 0_2
Time 20ms: Memtable 3 flushing → Level 0_3
Time 30ms: Memtable 4 flushing → Level 0_4 (now Level 0 full)
Time 40ms: Compaction starts (Level 0 → Level 1)
Time 50ms: Compaction still running...
Time 60ms: Compaction finishes, Level 0 now has 2 files

Problem: If compaction can't keep up, read-amp degrades
  More files to check per read
  Solution: reduce write rate, or add more compaction threads
```

---

## When to Use Which

```
Write-heavy, time-series data (metrics, logs)?
  → LSM (RocksDB, Cassandra, InfluxDB)
  → Write-amp: 2-4x (acceptable for this use case)
  → Compression: LSM compacts well (sorted data)

Read-heavy OLTP (user lookups, transactions)?
  → B-tree (PostgreSQL, MySQL)
  → Write-amp: 10-100x, but rare writes
  → Read latency: <50ms, predictable

Mixed (some of both)?
  → B-tree (PostgreSQL) if read/write ratio > 1:1
  → LSM if write/read ratio > 1:5
  → Hybrid (RocksDB) if you can tolerate higher space-amp
```

---

## Q&A

**Q1: Why does compaction hurt throughput?**

A: "Compaction reads old SSTables and writes new ones, stealing I/O bandwidth from incoming requests. If you have 1 disk with 1GB/s capacity, and compaction uses 500MB/s, only 500MB/s left for serving reads. Solution: separate compaction thread, SSD, or tiered compaction (write-amp trade-off)."

**Q2: Should I tune compaction aggressiveness?**

A: "Trade-off: aggressive compaction = lower read latency (fewer levels), but higher I/O during compaction. Conservative compaction = lower I/O cost, but reads slower. Start with default (RocksDB: 10 for leveled ratio), measure read/write latency, adjust based on your workload."

**Q3: How do bloom filters reduce read-amp?**

A: "Bloom filter (1 per SSTable) is a bit array. When looking up a key, query bloom filter first (O(1)). If negative = key definitely not in this SSTable (skip it). If positive = maybe in this SSTable (must check). In practice, 1-2% false positive rate, so you skip 98% of SSTables. Reduces read-amp by ~50%."

**Q4: What happens during LSM compaction to concurrent reads?**

A: "Compaction reads old files, writes new files, deletes old files. Concurrent reads may be reading old files while compaction is merging them. Most LSM engines use versioning: snapshots of the file list. Reads see a consistent view, compaction happens in background without blocking."

**Q5: Can a B-tree have lower write-amp than LSM?**

A: "No. B-tree write-amp grows with tree height (log N). For 1B records, tree height ~30, write-amp ~60x. LSM is fundamentally write-optimized. Trade-off: B-tree has lower space-amp and lower read-amp, LSM is opposite."

---

## Key Takeaways

1. **B-trees** = optimized for reads, write-amp scales with log(N)
2. **LSM** = optimized for writes, read-amp scales with number of levels
3. **Write-amp formula (B-tree):** ~(1 + log N) × 2, easily 10-100x
4. **Write-amp formula (LSM):** ~(1 + log_ratio(N)), typically 2-10x
5. **Compaction** is the cost of keeping LSM sorted (background merge)
6. **Space-amp** during compaction can be 2-3x (temporary)
7. **Bloom filters** reduce read-amp by skipping non-matching SSTables
8. **Hybrid approach** (e.g., PostgreSQL + RocksDB) sometimes best

---

## Interview Section

**Numeric 1:** You have a B-tree with 1M records (5 bytes per key, 1000 keys per node). Tree height is log_1000(1M) = 2. When you insert a key into a full leaf, how many nodes are rewritten?

*Working:*
- Insert into full leaf → split leaf (2 nodes written)
- Promote middle key to parent
- Parent becomes full? → split parent (2 more nodes)
- Tree height 2 → max 2 splits
- Total: ~4 nodes rewritten
- Write-amp: 4 writes / 1 logical insert = 4x

**Numeric 2:** An LSM has 10 levels (Tiered). At each level, files are 64MB. Level 0 flushes to Level 1 (merging with existing Level 1 files). Estimate total bytes read and written during one Level 0→1 compaction.

*Working:*
- Level 0: 4 files × 64MB = 256MB read
- Level 1: might have 4 files × 64MB = 256MB read (need to merge)
- Total read: 512MB
- Output: merged 512MB written to new Level 1 files
- Write-amp: 512MB written / 256MB input = 2x
- But only the Level 0 "input" counts as logical write, so it's 256MB / 256MB = 1x per level

**Scenario:** You're optimizing a time-series DB (100K inserts/sec, 10K reads/sec). Measurements show P99 read latency is 200ms, write latency is 1ms. Compaction is running constantly, using 50% disk bandwidth. Should you switch to B-tree?

*Analysis:*
- LSM: read-amp is high (200ms), write is fast (1ms)
- 100K inserts/sec is heavy write load (need LSM)
- Compaction stealing bandwidth hurts reads
- Switch to B-tree? No, would make writes 10-50x slower (10-50ms), unacceptable
- Instead: add disk bandwidth, or reduce write load, or shard data (separate B-trees per shard)

---

## Checklist

- [ ] Understand B-tree node splits and cascade effect on write-amp
- [ ] Know LSM levels, flushing, and compaction strategy differences
- [ ] Can estimate write-amp for a given tree height or LSM level count
- [ ] Understand bloom filters reduce read-amp by skipping files
- [ ] Can reason about when compaction I/O contention hurts performance
- [ ] Know the trade-off: better reads (B-tree) vs better writes (LSM)

## Common Wrong Answers

- "B-trees are always faster" ← Wrong, they're read-optimized, writes stall
- "LSM compaction is free" ← Wrong, it uses significant I/O bandwidth
- "Just add more memory to reduce compaction" ← Doesn't help if you have more data than memory
- "Write-amp doesn't matter, disks are fast" ← Wrong, write-amp on fast SSD still matters (wear out SSDs faster)
- "Bloom filters guarantee no read misses" ← Wrong, they have 1-2% false positive rate
