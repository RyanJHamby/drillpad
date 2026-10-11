# Benchmarking Data Structures: When Theory Fails

## Theory vs Reality

Theory says: Red-Black tree is O(log N), Hash table is O(1).

Reality: Hash table might be 10x slower than Red-Black tree.

Why?

## Cache Hierarchy Matters More Than Big-O

```
CPU cache levels:
  L1: 32 KB, 4 cycles latency
  L2: 256 KB, 12 cycles latency
  L3: 8 MB, 40 cycles latency
  RAM: 16 GB+, 200+ cycles latency

One cache miss = 5 nanoseconds × 200 = 1 microsecond
= 1000 CPU cycles wasted

On 3GHz CPU:
  - Hit in L1: 4 cycles (0.001 microseconds)
  - Hit in L3: 40 cycles (0.013 microseconds)
  - Hit in RAM: 200+ cycles (0.06 microseconds)
```

A cache miss costs more than the actual algorithm!

## Example: Hash Table vs B-tree

```cpp
// Hash table lookup
struct HashTable {
    Node** buckets;  // Scattered in memory
    size_t size;
};

// Lookup 1000 keys:
for (int i = 0; i < 1000; i++) {
    int hash = key[i] % size;
    Node* n = buckets[hash];  // Random memory access → CACHE MISS
    while (n && n->key != key[i]) {
        n = n->next;  // Another random access → CACHE MISS
    }
}
```

**Reality:** Lots of cache misses (buckets array is scattered).

```cpp
// B-tree lookup
struct BNode {
    int keys[32];
    BNode* children[33];
};

// Lookup 1000 keys:
for (int i = 0; i < 1000; i++) {
    BNode* node = root;
    while (!node->is_leaf) {
        int idx = binary_search(node->keys, key[i]);
        node = node->children[idx];  // 4 levels deep, 4 cache accesses total
    }
}
```

**Reality:** Fewer cache misses (B-node is 650 bytes, one cache line per level).

## Realistic Benchmark: Hash Table vs B-tree

```
Scenario: 1M insertions, random keys

Theory:
  Hash table: 1M * O(1) = 1M operations
  B-tree: 1M * O(log N) = 1M * 20 = 20M operations
  
  Winner: Hash table (20x fewer ops)

Real benchmark (on Intel i9):
  Hash table:  2.3 seconds
  B-tree:      0.8 seconds
  
  Winner: B-tree (3x faster!)
```

Why? Cache efficiency dominates the O(log N) overhead.

## How to Benchmark Correctly

### Step 1: Measure CPU Cycles, Not Seconds

```cpp
#include <x86intrin.h>

uint64_t start = __rdtsc();
for (int i = 0; i < 1M; i++) {
    lookup(key[i]);
}
uint64_t end = __rdtsc();

uint64_t cycles = end - start;
double ns_per_op = cycles * 1000 / 1M / cpu_ghz;
```

Seconds are too coarse (background processes mess with timing).

### Step 2: Measure Cache Misses

```bash
perf stat ./benchmark

# Output:
# 1,234,567 instructions
# 23,456 cache-references
# 1,234 cache-misses         ← This is KEY
# 1.23 GHz effective clock speed
```

Cache misses explain 80% of performance differences.

### Step 3: Test with Real Data Sizes

```cpp
// What fits in CPU cache?
L1: 32 KB → ~4,000 keys
L3: 8 MB → ~1M keys

// Benchmark different sizes:
benchmark(size=1K);    // Fits in L1
benchmark(size=100K);  // Fits in L3
benchmark(size=1M);    // Hits RAM
```

Performance cliff when data exceeds cache size.

### Step 4: Measure Percentiles, Not Averages

```cpp
vector<uint64_t> latencies;
for (int i = 0; i < 100K; i++) {
    latencies.push_back(lookup(key[i]));
}

sort(latencies.begin(), latencies.end());

cout << "P50: " << latencies[50K] << " ns\n";
cout << "P99: " << latencies[99K] << " ns\n";
cout << "P99.9: " << latencies[99900] << " ns\n";
```

Average latency is useless (one slow outlier ruins everything).

## Interview Pattern: Real-World Performance

```
Q: "You're choosing between hash table and B-tree for 10M keys.
   Which is faster?"

Weak answer:
  "Hash table, O(1) vs O(log N)"
  (❌ Ignores cache)

Strong answer:
  "Measure with real data, but I'd guess B-tree:
  
  1. Theory favors hash table (O(1))
     But theory ignores cache hierarchy
  
  2. In practice:
     - Hash table: random memory access → cache misses
     - B-tree: sequential access → cache hits
     - Cache miss = 1000x slowdown vs cache hit
  
  3. For 10M keys:
     - Hash table: ~100 bytes per key → 1GB memory (doesn't fit in cache)
     - B-tree: ~40 bytes per key → 400MB (fits in L3)
     - B-tree stays in cache, hash table doesn't
  
  4. Benchmarking approach:
     - Implement both
     - Measure with perf: time + cache-misses
     - Test different data sizes (1K, 100K, 1M, 10M)
     - Measure P99 latency (not average)
  
  5. Expected result:
     - Hash table fast for <100K keys (fits in L3)
     - B-tree faster for >1M keys (cache dominates)
     - Tipping point: ~500K keys
  
  6. For production (10M keys):
     - B-tree is probably 2-3x faster
     - Test with real workload to confirm"

Why this signals good judgment:
  - You understood cache beats algorithm
  - You'd measure instead of guessing
  - You tested different scales
  - You measured percentiles
```

## Production Benchmarking Checklist

- [ ] Measure CPU cycles (perf stat)
- [ ] Measure cache misses (perf list cache-references)
- [ ] Test multiple data sizes
- [ ] Measure percentiles (P50, P99, P99.9)
- [ ] Warm up caches (discard first N iterations)
- [ ] Use realistic data (not synthetic)
- [ ] Compare multiple candidates
- [ ] Document hardware (CPU, RAM, etc.)
- [ ] Re-test on target hardware (laptops ≠ servers)

## What This Signals

- You understand cache hierarchy matters more than Big-O
- You've actually benchmarked (not just theorized)
- You measure cache misses and latency percentiles
- You test on real data sizes and hardware
