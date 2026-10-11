# Hash Tables: Collision Handling, Load Factor, Resizing

## The Basics (Interview Signal)

```
Hash table: O(1) lookup

But:
  - Collisions happen (two keys hash same)
  - Load factor matters (size vs capacity)
  - Resizing is expensive

Interview question: "Why is your hash table slow at scale?"
Bad answer: "IDK, hash tables are O(1)"
Good answer: "Collisions or load factor > 0.7"
```

## Collision Handling

```
1. Chaining (linked list at each bucket)
  hash("alice") % 10 = 3
  bucket[3] = [("alice", 50), ("bob", 30)] (collision)
  
  Pro: Simple, handles unlimited collisions
  Con: Cache-unfriendly (follow pointers)
  
2. Open addressing (probe for next empty)
  hash("alice") % 10 = 3 (occupied)
  Try 4, 5, 6 until empty
  
  Pro: Cache-friendly (contiguous)
  Con: Complex deletion, clustering
  
3. Robin Hood (steal if better probe sequence)
  hash("alice") % 10 = 3 (taken by younger key)
  Swap: Alice takes 3, displaced key continues probing
  
  Pro: Reduces variance, better distribution
  Con: Complex implementation
```

## Load Factor

```
Load factor = items / capacity

At 0.5: ~50% full, low collisions, high memory waste
At 0.75: ~75% full, balanced
At 0.9: ~90% full, high collisions, slow lookups

Typical strategy: Resize when load factor > 0.75
```

## Trading Interview: Hash Table Bottleneck

```
Q: "Order book stores orders by ID in hash table. Why slow?"

Weak answer:
  "Hash tables are O(1), should be fast"
  (❌ Ignores real constraints)

Strong answer:
  "At 1M orders, hash table performance depends on:
  
  1. Load factor
     If capacity = 1M, load = 0.5, collision rate low
     If capacity = 100k, load = 10, massive collisions
     
  2. Hash function
     If poor hash, clustering → linear probe time
     
  3. Memory access
     Chaining: cache misses (follow pointers)
     Open addressing: cache hits (contiguous)
     
  Measurement:
     - Monitor collision rate (avg probe length)
     - Monitor cache miss rate (perf stat)
     
  Solution:
     - If load factor high: resize earlier
     - If collisions high: better hash function
     - If cache misses high: open addressing"
```

## When Theory Breaks

```
Theory: Hash table O(1), array O(n)
Reality at 10M items:

Hash table (chaining):
  - Collision chain = 5 items
  - Follow 5 pointers = 5 cache misses
  - Each miss = 200ns
  - Total: 1000ns per lookup
  
Array (linear search):
  - Scan 10M items sequentially
  - Cache-friendly (prefetch)
  - 10M * 1ns = 10ms
  
Result: Array might be faster for scans!

This is why databases use B-trees (hybrid):
  - Tree structure: O(log n)
  - Node-level scan: cache-friendly
  - Best of both worlds
```

