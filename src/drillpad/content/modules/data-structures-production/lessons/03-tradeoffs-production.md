# Production Tradeoffs: Memory vs Speed vs Complexity

## The Core Triangle

Every data structure is a tradeoff:

```
          Speed
         /      \
    Simple --- Memory
```

Pick 2 out of 3.

## Examples

### Example 1: Array vs Linked List

```
Array: [1, 2, 3, 4, 5]
  - Lookup: O(1) (just index)
  - Insert: O(N) (shift all elements)
  - Memory: Dense (no pointers)
  - Complexity: Simple

Linked List: 1 → 2 → 3 → 4 → 5
  - Lookup: O(N) (traverse)
  - Insert: O(1) (just link)
  - Memory: Loose (pointers per node)
  - Complexity: Medium
```

**When to use:**
- Need fast lookup: Array
- Need fast insert: Linked List

### Example 2: Hash Table vs B-tree

```
Hash Table (in-memory):
  - Lookup: O(1) average
  - Insert: O(1) average
  - Memory: Loose (hash overhead, collisions)
  - Speed: Fast
  - Complexity: Simple
  
B-tree (disk-optimized):
  - Lookup: O(log N)
  - Insert: O(log N)
  - Memory: Dense (cache-efficient)
  - Speed: Medium
  - Complexity: Medium (rebalancing)
```

**Trade:** Hash table is faster but hash lookup is simpler than B-tree navigation.

### Example 3: Bloom Filter vs Hash Set

```
Bloom Filter:
  - Lookup: O(K) where K = hash functions
  - Insert: O(K)
  - Memory: Very compact (bit array)
  - False positive: Possible (but rate is tunable)
  - Complexity: Simple
  
Hash Set:
  - Lookup: O(1) average
  - Insert: O(1) average
  - Memory: Normal (hash table size)
  - False positive: None
  - Complexity: Simple
```

**Trade:** Bloom filter uses 8x less memory but has false positives.

## Memory vs Speed Tradeoff

### Memory Overhead: Why It Matters

```
Hash table with 1M entries:
  - Key size: 100 bytes
  - Value size: 100 bytes
  - Hash overhead: ~50% extra space
  
  Total: 1M * 200 * 1.5 = 300MB

If you have 100 such tables: 30GB

Server with 32GB RAM: Can only fit 1-2 tables in cache.
Hits disk → 1000x slower.
```

**Solution:** Choose dense structure.
- B-tree: 90% memory efficiency
- LSM: 95% memory efficiency (better than B-tree)
- Hash table: 50% efficiency (for comparison)

### Speed vs Memory Tradeoff

```
If memory cheap:
  - Use large hash table (no collisions)
  - O(1) lookup
  
If memory expensive:
  - Use B-tree (90% efficient)
  - O(log N) lookup (slower but fits in RAM)
  
If VERY limited memory:
  - Use Bloom filter or bitset
  - Approximate answers (accept false positives)
```

## Complexity vs Speed

### Example: Cache-Conscious B-tree vs Red-Black Tree

```
Red-Black Tree (simple, balanced):
  struct RBNode {
    int key;
    void* value;
    RBNode* left;
    RBNode* right;
    Color color;  // + 8 bytes
  };
  
  Each node: 40 bytes
  Lookup 1M keys: 20 levels * 3 pointers per level → 60 cache misses

B-tree (complex, dense):
  struct BNode {
    int keys[32];      // 128 bytes
    void* values[32];  // 256 bytes
    BNode* children[33]; // 264 bytes
    bool is_leaf;      // 1 byte
  };
  
  Each node: 650 bytes
  Lookup 1M keys: 4 levels * 1 pointer per level → 4 cache misses
```

**Trade:** B-tree is more complex (rebalancing) but 15x faster (fewer cache misses).

## Interview Pattern: Structure Selection

```
Q: "You're caching 1B URLs (each 100 bytes).
   Memory budget: 10GB.
   Need to check if URL is in cache in < 100 microseconds.
   What structure?"

Weak answer:
  "Hash table (O(1) lookup)"
  (❌ Uses 100GB, doesn't fit)

Strong answer:
  "Bloom filter with compression, not hash table.
  
  1. Memory calculation:
     - Hash table: 1B URLs * 100 bytes + overhead = ~150GB
     - Won't fit in 10GB
  
  2. Bloom filter calculation:
     - 1B items, 1% false positive rate
     - Space: log2(1/0.01) * N / 8 = 10 bits per item
     - Total: 1B * 10 bits / 8 = 1.25GB
     - Fits in 10GB!
  
  3. Tradeoff:
     - 1% false positives (URL marked in cache when it's not)
     - But: 99% accuracy is fine (cache miss is cheap)
     - Cost: 1 false check for every 99 hits
  
  4. Performance:
     - Lookup: O(K) where K = 7 hash functions
     - ~5-10 microseconds per check
     - Fits latency budget
  
  5. If 10GB still too tight:
     - Use Cuckoo filter (similar memory, better lookup)
     - Or: Use bitset (even tighter, just store URL hashes)
  
  6. If we had 100GB memory:
     - Use hash table (simpler, no false positives)
     - Still 5-10 microseconds per lookup"

Why this signals good judgment:
  - You calculated memory footprint
  - You knew Bloom filter is for memory-constrained scenarios
  - You accepted false positives when rational
  - You understood the tradeoff
```

## Checklist: Choosing Production Structure

**Step 1: Measure constraints**
- [ ] How much memory do I have?
- [ ] How many operations/second?
- [ ] What latency budget?
- [ ] Read vs write ratio?

**Step 2: Calculate footprints**
- [ ] Hash table: N * (key + value + 50% overhead)
- [ ] B-tree: N * (key + value + 10% overhead)
- [ ] Bloom filter: N * 10 bits (for 1% FP rate)

**Step 3: Match constraints**
- [ ] Does it fit in memory?
- [ ] Does it meet latency?
- [ ] Is complexity acceptable?

**Step 4: Verify assumptions**
- [ ] Benchmark against real data
- [ ] Profile cache misses
- [ ] Monitor real-world performance

## Common Mistakes

| Mistake | Cost | Fix |
|---|---|---|
| **Hash table for 1B items** | 150GB memory (doesn't fit) | Use Bloom filter or B-tree |
| **Linked list for frequent lookup** | O(N) on 1M items = 1ms | Use array or hash table |
| **Red-Black tree at scale** | Cache misses, 10x slower | Use B-tree (fewer nodes) |
| **No compression** | 10x more memory than needed | Use Bloom filter or bitset |

## What This Signals

- You've built systems with real memory constraints
- You calculate memory footprint (not theoretical)
- You know when approximate structures (Bloom) are valuable
- You understand cache hierarchy (B-tree wins)
