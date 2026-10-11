# Tree Variants: B-tree, LSM, Skiplist, Tries

## Why Trees Matter in Production

Trade-off: Fast lookup vs. Efficient storage vs. Fast updates

Different trees optimize for different things:

| Tree | Lookup | Insert | Space | Best For |
|---|---|---|---|---|
| **B-tree** | O(log N) | O(log N) | Dense | Databases |
| **LSM** | O(log N) avg | O(1) amort | Compact | Write-heavy (RocksDB) |
| **Skiplist** | O(log N) | O(log N) | Loose | In-memory, simple |
| **Trie** | O(K) | O(K) | Loose | Strings, IP routing |

## B-Tree: Balanced & Cache-Friendly

```
B-tree node stores multiple keys:
      [5, 15, 25]
     /     |      \
[1,3]  [7,10,12] [20,22] [30,40]
```

**Why B-trees:**
- Disk-optimized: One node = one disk page
- Read 4KB at a time, get 100s of keys
- Fewer seeks = faster query

**Structure:**
- Each node has M keys (not just 1)
- Each node has M+1 children
- All leaves at same depth

**Cost: Insert/Delete require rebalancing**

```cpp
struct BTreeNode {
    int keys[M];           // Store multiple keys
    BTreeNode* children[M+1];
    bool is_leaf;
};
```

**Real use:** PostgreSQL, MySQL (InnoDB), SQLite all use B-trees

## LSM Tree: Write-Optimized (Log-Structured Merge)

Problem: B-tree insert requires seeking (slow on disk).

Solution: LSM appends all writes to a log, merges periodically.

```
Level 0 (in-memory, hot):
  MemTable: [new writes, fast append]
  Size: 100MB

When MemTable full:
  Flush to Level 1: [immutable sorted file]

Level 1: Size 100MB
  Multiple files, maybe 10x100MB
  
Level 2: Size 1GB
  100x10MB files, larger
  
...merge happens in background...
```

**Write flow:**
1. Write to MemTable (in-memory log): O(1)
2. MemTable full → Compaction (background)
3. Reads: Check MemTable, then Level files

**Why LSM wins at writes:**
- Writes are sequential appends (fast on disk)
- Merge happens in background (don't block user)
- Typical: 10x faster write throughput than B-tree

**Cost:**
- Reads are slower (check multiple levels)
- Compaction creates I/O spikes
- Space overhead (temporary copies during merge)

**Real use:** RocksDB, LevelDB, Cassandra, HBase

## Skiplist: Simplicity in Production

Probabilistic alternative to balanced trees:

```
Level 3:       [15]
               /  \
Level 2: [5] [15] [25]
         / \ /  \ /  \
Level 1: [5][10][15][20][25][30]
         all nodes linked forward
```

**Insertion:**
- Flip coin at each level to decide height
- Insert at appropriate levels
- No rebalancing needed!

**Properties:**
- O(log N) lookup (like B-tree)
- O(log N) insert (like B-tree)
- Much simpler code (no rebalancing)
- Probabilistic balance (usually good, might be unlucky)

**Real use:** Redis, Memcached sorted sets

## Trie: String-Optimized

```
        root
       / | \
      a  b  c
     /    \   \
    p      a  cat
   /        \
  p         t
  |
[apple]  [bat]  [cat]
```

**Best for:**
- Autocomplete ("aaa" prefix → [aaaaaa, aaa])
- IP routing (longest prefix match)
- Spell checking

**Lookup:** O(K) where K = string length (not O(log N) comparisons)

**Cost:** Loose space (may have 26 pointers per node for alphabet)

## Production Hybrid: LSM + B-tree Cursor

Real databases use multiple structures:

```
PostgreSQL (B-tree):
  - Inserts are slower but reads are very fast
  - Good for balanced workload

RocksDB (LSM):
  - Writes are 10x faster
  - Reads are slower but still O(log N)
  - Good for write-heavy workloads

Hybrid approach:
  - Write-hot data: LSM
  - Read-hot data: B-tree
  - Rebalance periodically
```

## Interview Pattern: Choosing Data Structure

```
Q: "You're building a logging system. 100K events/sec.
   Users query: 'Show logs from 2024-01-15'.
   What data structure?"

Weak answer:
  "Use a B-tree"
  (❌ Writes are slow)

Strong answer:
  "LSM tree (write-optimized):
  
  1. Workload analysis:
     - Write: 100K events/sec (write-heavy)
     - Read: occasional queries (not real-time)
     - Retention: keep 1 year of logs
  
  2. Why LSM:
     - Sequential writes to log (fast, disk-optimized)
     - Compaction merges levels (don't block writes)
     - Reads are still O(log N), acceptable for batch queries
  
  3. Implementation detail:
     - MemTable flushes to Level 0 every 100ms
     - Background compaction merges levels
     - Bloom filters prevent unnecessary seeks
  
  4. Estimated performance:
     - Write latency: 1-10ms (sequential append)
     - Query latency: 100-500ms (scan levels for date range)
     - Throughput: 100K writes/sec (sustainable)
  
  5. Monitoring:
     - Watch compaction time (if > 1s, lagging)
     - Track query latency (should be <1s)
     - Monitor disk I/O (compaction creates spikes)
  
  Alternative if reads were real-time:
    B-tree with write buffer
    - Batch writes to buffer
    - Periodic flush to B-tree
    - Reads hit B-tree directly"

Why this signals good judgment:
  - You matched structure to workload
  - You understood write vs read tradeoffs
  - You knew LSM's background compaction benefit
  - You considered bloom filters (real LSM feature)
```

## Comparison Table

| Structure | Read | Write | Space | When |
|---|---|---|---|---|
| **B-tree** | ✓ Fast | Slow | Efficient | Balanced, reads matter |
| **LSM** | OK | ✓ Fast | Loose | Write-heavy logs |
| **Skiplist** | ✓ Fast | ✓ Fast | Loose | In-memory sorted sets |
| **Trie** | ✓ Fast (K) | ✓ Fast (K) | Loose | Strings, prefixes |

## What This Signals

- You've chosen structures for real workloads
- You understand write vs read tradeoffs
- You know why databases use each (not arbitrary)
- You think about disk I/O and memory hierarchy
