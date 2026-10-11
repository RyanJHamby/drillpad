# Hashing & Data Structures: Consistent Hashing, Bloom Filters, Skip Lists

## Typical Contexts: payments, cloud platforms, and trading systems

**Problem:** You have data distributed across N servers. When you add a new server, which keys move?

- **Bad:** Hash all keys again → every key rehashed → all servers overloaded
- **Better:** Consistent hashing → only 1/N keys move (minimal impact)

**And:** Is this key in my cache? Check bloom filter (fast negative answer, no disk lookup).

**And:** Need sorted concurrent access? Skip list (simpler than B-tree, faster than mutex+array).

---

## Consistent Hashing

```
Regular hashing (hash % N):
  N = 3 servers (A, B, C)
  Key "user:123" → hash("user:123") % 3 = 1 → Server B
  
  Add server D (N = 4):
  Key "user:123" → hash("user:123") % 4 = 0 → Server A
  KEY MOVED! All keys rehashed → cache miss, rebalance nightmare

Consistent hashing (ring):
  Place servers on ring (hash(server_name) mod 2^32)
  Place key on ring (hash(key) mod 2^32)
  Key "lives" at next server clockwise
  
  Example:
  Ring: [0 ← 2^32]
    Server A at position 100
    Server B at position 200
    Server C at position 300
    Key "user:123" hashes to 150
      → clockwise: next is Server B (200)
      → Key lives on Server B
  
  Add Server D at position 250:
    Key "user:123" (150) still goes clockwise
    → now next is Server D (250)
    KEY MOVED! But:
    - Only keys between C (300) and D (250) move
    - Other keys stay put
    - Instead of ALL keys moving, only ~1/4 move
```

---

## Consistent Hashing Implementation

```python
import bisect
import hashlib

class ConsistentHashRing:
    def __init__(self, replicas=3):
        """
        replicas: virtual nodes per server (for load balancing)
        """
        self.replicas = replicas
        self.ring = {}  # position -> server
        self.sorted_keys = []  # sorted positions
    
    def _hash(self, key):
        """Hash key to position on ring."""
        return int(hashlib.md5(str(key).encode()).hexdigest(), 16)
    
    def add_server(self, server):
        """Add server to ring."""
        for i in range(self.replicas):
            position = self._hash(f"{server}:{i}")
            self.ring[position] = server
            self.sorted_keys.append(position)
        self.sorted_keys.sort()
    
    def remove_server(self, server):
        """Remove server from ring."""
        for i in range(self.replicas):
            position = self._hash(f"{server}:{i}")
            del self.ring[position]
            self.sorted_keys.remove(position)
    
    def get_server(self, key):
        """Find server for key (clockwise)."""
        if not self.sorted_keys:
            return None
        
        position = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, position)
        
        if idx == len(self.sorted_keys):
            idx = 0  # wrap around
        
        return self.ring[self.sorted_keys[idx]]
    
    def rebalance_impact(self, new_server):
        """Estimate % of keys that will move."""
        # Keys between previous server and new server
        # With perfect ring, ~100% / N servers = ~1/N move
        return 100.0 / len(set(self.ring.values()))

# Usage
ring = ConsistentHashRing(replicas=3)
ring.add_server("server_a")
ring.add_server("server_b")
ring.add_server("server_c")

print(ring.get_server("user:123"))  # "server_b"
print(ring.get_server("user:456"))  # "server_a"

# Add new server
ring.add_server("server_d")
print(f"Impact: {ring.rebalance_impact('server_d'):.1f}% keys move")
```

---

## Bloom Filter (Set Membership, No False Negatives)

```
Problem: Is key "user:123" in my cache?
  Naive: query cache (disk hit = slow)
  Better: bloom filter (memory, fast)

Bloom filter:
  ├─ Bit array of size M (e.g., 1M bits = 125KB)
  ├─ K hash functions (e.g., 3)
  ├─ Add: set bits h1(key), h2(key), h3(key) to 1
  └─ Check: all 3 bits are 1? → probably in set
             any bit is 0? → definitely NOT in set

Example:
  M = 8, K = 3, hash functions: f1, f2, f3
  
  Add "user:123":
    f1("user:123") mod 8 = 2 → set bit[2]
    f2("user:123") mod 8 = 5 → set bit[5]
    f3("user:123") mod 8 = 7 → set bit[7]
    Bit array: [0,0,1,0,0,1,0,1]
  
  Check "user:123":
    f1("user:123") mod 8 = 2 → bit[2] = 1 ✓
    f2("user:123") mod 8 = 5 → bit[5] = 1 ✓
    f3("user:123") mod 8 = 7 → bit[7] = 1 ✓
    Result: PROBABLY in set
  
  Check "user:999":
    f1("user:999") mod 8 = 1 → bit[1] = 0 ✗
    Result: DEFINITELY NOT in set (no false negatives!)
    
False positive rate: ~1.4% with optimal K
```

---

## Bloom Filter Implementation

```python
import hashlib
import math

class BloomFilter:
    def __init__(self, expected_elements, false_positive_rate=0.01):
        """
        expected_elements: N items to add
        false_positive_rate: acceptable FP rate (1% = 0.01)
        """
        # Optimal bit array size
        self.m = int(-1 * expected_elements * math.log(false_positive_rate) / (math.log(2)**2))
        
        # Optimal number of hash functions
        self.k = int(self.m / expected_elements * math.log(2))
        
        self.bits = [False] * self.m
    
    def _hash(self, item, seed):
        """Hash item with seed."""
        h = hashlib.md5(f"{item}:{seed}".encode()).digest()
        return int.from_bytes(h, 'big') % self.m
    
    def add(self, item):
        """Add item to filter."""
        for i in range(self.k):
            idx = self._hash(item, i)
            self.bits[idx] = True
    
    def contains(self, item):
        """Check if item might be in filter (may have false positives)."""
        for i in range(self.k):
            idx = self._hash(item, i)
            if not self.bits[idx]:
                return False  # Definitely not in set
        return True  # Probably in set
```

---

## Skip List (Concurrent Sorted Access)

```
Problem: Need fast sorted access + concurrency.
  B-tree: complex, hard to make lock-free
  Skip list: simple, naturally concurrent
  
Skip list structure:
  Level 3:     [1] ────────────────────────── [100]
  Level 2:     [1] ────── [50] ────────────── [100]
  Level 1:     [1] ── [25] ── [50] ── [75] ── [100]
  Level 0:  [1] - [10] - [25] - [50] - [75] - [100]
  
Search for 75:
  1. Start at top level (3), position 1
  2. Can I jump to 100? (100 > 75) No, advance
  3. No more nodes, go down to level 2
  4. Can I jump to 50? (50 < 75) Yes, jump
  5. Can I jump to 100? (100 > 75) No
  6. Go down to level 1
  7. Find 75
  
Time: O(log N) average
Space: O(N) (like balanced tree)
```

---

## Skip List vs B-Tree vs Balanced BST

```
                  Latency    Concurrency  Code Complexity
B-tree            O(log N)   Hard         High (rebalancing)
Red-Black tree    O(log N)   Hard         Medium (rotations)
Skip List         O(log N)   Easy         Low (random levels)
Hash Map          O(1)       Medium       Medium (resize)

Skip lists are:
  + Simple to implement
  + Natural concurrency (levels independent)
  + No rotation/rebalancing
  - Slightly more memory (due to levels)
  
Used in: ConcurrentSkipListMap (Java), LevelDB (database)
```

---

## Real Example: Cache with Bloom Filter (Negative Caching)

```python
class BloomFilterCache:
    def __init__(self, capacity=1000):
        self.cache = {}  # actual cache
        self.bloom = BloomFilter(expected_elements=capacity)
    
    def get(self, key):
        """Get value, avoiding disk lookup if definitely not cached."""
        
        # Quick check: bloom filter says no
        if not self.bloom.contains(key):
            return None  # Definitely not in cache
        
        # Might be in cache (false positive possible)
        return self.cache.get(key)
    
    def set(self, key, value):
        """Set value in cache."""
        self.cache[key] = value
        self.bloom.add(key)

# Usage: reduce disk I/O
cache = BloomFilterCache()
cache.set("user:123", {"name": "Alice"})

# Check 10K times
for i in range(10000):
    result = cache.get(f"user:{i}")
    if not result:
        # Would normally query database
        # Bloom filter avoids 99% of queries for non-existent keys
        pass
```

---

## Design Decisions

**Why consistent hashing over regular hash?**
- Regular: all keys rehash when adding server
- Consistent: only 1/N keys rehash
- In production: 1/N rebalance is huge saving

**Why bloom filter?**
- Negative assertion (key definitely NOT present) is fast
- Regular hash map requires lookup (disk hit if not present)
- Bloom: memory, no false negatives, acceptable false positives

**Why skip list?**
- Simpler than B-tree (no rebalancing)
- Better cache locality than linked list
- Natural concurrency (levels can be locked independently)

---

## Q&A

**Recall 1:** Consistent hashing ring has 10 servers. Add 1 server. What % of keys move?

*Must-say:*
- Perfect ring: 1/11 ≈ 9% move
- With replicas (3): same, 9% move
- With non-uniform distribution: could be up to 20%

**Probe 1:** Bloom filter has FP rate 1%. You query 10K non-existent keys. How many false positives?

*Expected:*
- 10K queries * 1% = ~100 false positives
- You'd do 100 unnecessary disk lookups
- To reduce: increase bloom filter size (trade memory for lower FP rate)

**Numeric 1:** Skip list with 4 levels. Search for element. Expected comparisons?

*Working:*
- Start at top (level 3): ~N/8 nodes, 1 comparison
- Go to level 2: ~N/4 nodes, 1 comparison
- Go to level 1: ~N/2 nodes, 1 comparison
- Go to level 0: ~N nodes, 1 comparison
- Total: 4 comparisons = O(log N) with N=16

---

## Questions for the Interviewer

- Do you use consistent hashing? (for sharding?)
- How do you handle rebalancing? (online, offline?)
- Do you use bloom filters? (for what use case?)
- Have you encountered consistent hashing edge cases? (hot spots?)
- Do you use skip lists? (or B-trees?)
- What's your false positive rate tolerance for bloom filters?

