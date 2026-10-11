# Indexing Strategies: B-Trees, Hash Indexes, and LSM Trees

## Overview

Indexes are what make databases fast. This lesson covers:
1. Why sequential scans are slow
2. B-tree indexes (most databases use these)
3. Hash indexes (fast lookups, no range queries)
4. LSM trees (write-optimized, used in RocksDB/Cassandra)
5. When to use each

---

## The Problem: Sequential Scan is Slow

Without an index:

```
Query: SELECT * FROM users WHERE user_id = 12345

Execution:
  Read row 0: Is it 12345? No.
  Read row 1: Is it 12345? No.
  ...
  Read row 1,000,000: Is it 12345? Yes!
  
Cost: 1M disk seeks (each ~5ms) = 5,000 seconds = way too slow
```

**With index:**

```
Query: SELECT * FROM users WHERE user_id = 12345

Execution:
  Lookup in B-tree: O(log 1M) = 20 steps
  Each step: 1 disk seek (~5ms)
  Total: 20 × 5ms = 100ms = acceptable
```

---

## B-Tree Indexes: The Default

B-trees are balanced search trees. Most databases use them (MySQL, PostgreSQL, MongoDB).

```
      [45]
     /    \
   [25]   [65]
   / \    /  \
 [10][30][55][80]

Insert 28:
1. Find leaf containing 28 (traverse tree)
2. Insert into leaf
3. If leaf is full, split and promote middle value up
4. Cost: O(log n) disk seeks
```

**Advantages:**
- Range queries work (find all ids between 100-200)
- Efficient insertion/deletion (self-balancing)
- Locality (nearby keys are physically close)

**Disadvantages:**
- Write amplification (splits cause rewrites)
- Space overhead (tree structure)

**Example query:**

```sql
-- Fast with B-tree (range query)
SELECT * FROM users 
WHERE user_id BETWEEN 1000 AND 2000;

-- B-tree: Find leftmost (1000), scan right until > 2000
-- Cost: O(log n + m) where m = 1000 results
```

---

## Hash Indexes: Fast Point Lookups

Hash indexes use a hash function to find rows directly.

```
Hash table: [key → disk_location]

lookup(user_id=12345):
  h = hash(12345) = 7
  location = hash_table[7]
  Read disk location → row data
  Cost: O(1) disk seeks (usually 1, maybe 2 with collisions)
```

**Advantages:**
- O(1) point lookups (fast)
- Minimal overhead

**Disadvantages:**
- No range queries (hash(100) and hash(101) are unrelated)
- Rehashing on growth (expensive)

**Example query:**

```sql
-- Fast with hash index (point lookup)
SELECT * FROM users WHERE user_id = 12345;  -- O(1)

-- SLOW with hash index (range query)
SELECT * FROM users WHERE user_id BETWEEN 1000 AND 2000;
-- Must scan entire hash table (defeats purpose)
```

---

## LSM Trees: Write-Optimized

LSM (Log-Structured Merge) trees are optimized for writes. Used in RocksDB, Cassandra.

```
Write path:
1. Write to in-memory buffer (memtable) — fast, O(1)
2. When full, flush memtable to disk as "SSTable" (sorted string table)
3. On read, check memtable, then all SSTables

Result: Writes are fast (just append to memory), but reads need to check multiple files.
```

**Advantages:**
- Sequential disk writes (fast even on HDDs)
- Efficient for write-heavy workloads
- Good compression (sorted data compresses well)

**Disadvantages:**
- Read amplification (check memtable + multiple SSTables)
- Write amplification during compaction (remerge files)
- Complexity (background compaction process)

**Example:**

```
Time 1: Write user_id=100 to memtable
Time 2: Write user_id=200 to memtable
Time 3: Memtable full → flush to SSTable_1 on disk
Time 4: Write user_id=50 to new memtable
Time 5: Read user_id=100
  - Check memtable (not found)
  - Check SSTable_1 (found!)
  - Cost: 2 lookups (worst case: number of SSTables)
```

---

## Choosing the Right Index

```
Point lookup (user_id = 123)?
  → Hash index (O(1))
  
Range query (user_id BETWEEN 100 AND 200)?
  → B-tree index (O(log n + m))
  
Write-heavy workload (100k writes/sec)?
  → LSM tree (sequential writes)
  
Read-heavy workload (100k reads/sec)?
  → B-tree with caching
  
Mixed workload?
  → B-tree (balanced, handles both reasonably)
```

---

## Index Trade-Offs

```
B-Tree:     Good reads, balanced writes, standard choice
Hash:       Fast point lookups, no range queries
LSM:        Fast writes, slower reads, complex compaction
```

**Real example:**

```sql
-- User ID lookup (point query, hash index is best)
CREATE INDEX idx_user_id_hash USING HASH ON users(user_id);
SELECT * FROM users WHERE user_id = 12345;  -- Fast

-- Date range query (range query, B-tree is best)
CREATE INDEX idx_created_at_btree ON users(created_at);
SELECT * FROM users WHERE created_at BETWEEN '2024-01-01' AND '2024-01-31';  -- Fast

-- Write-heavy append log (LSM is best)
INSERT INTO events (timestamp, value) VALUES (NOW(), data);  -- 100k inserts/sec → LSM
```

---

## Key Takeaways

1. **No index = full table scan** (O(n), painful)
2. **B-trees** = default choice (range + point queries)
3. **Hash indexes** = point lookups only
4. **LSM trees** = write-heavy workloads
5. **Index = trade-off** (storage vs speed vs write cost)

---

## Q&A

**Q: How much overhead does an index add?**

Storage: 10-30% of original data (B-tree has tree structure)
Write cost: 1x (write to index when writing data)

**Q: Can I have multiple indexes?**

Yes, but each adds overhead. Use EXPLAIN ANALYZE to see which indexes are actually used.

**Q: Why not just hash everything?**

Hash indexes can't do range queries, joins, or ordering. B-trees are slower on point lookups but handle more query patterns.
