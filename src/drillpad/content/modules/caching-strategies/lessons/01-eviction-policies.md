# Cache Eviction Policies: LRU, LFU, ARC

## The Problem

Cache has N slots. When full and new item arrives, which old item to remove?

```
Cache (4 slots): [A, B, C, D]
New item E arrives
Options:
  - Remove A (oldest: LRU)
  - Remove C (least used: LFU)
  - Remove B (adaptive: ARC)
```

## LRU (Least Recently Used)

Remove item not used for longest time.

```
Access pattern: A, B, C, D, A, E (cache full, add E)

Timeline:
  t=1: [A, _, _, _]
  t=2: [A, B, _, _]
  t=3: [A, B, C, _]
  t=4: [A, B, C, D]
  t=5: [A, B, C, D] (A is now "most recent")
  t=6: [A, B, C, E] (remove D, least recently used)

Next access pattern: D
  Cache miss (D was evicted)
  Cost: Go to memory, ~100ns
```

**Pros:**
- Simple (just track last access time)
- Good for temporal locality (if you used it recently, you'll use it again soon)

**Cons:**
- Bad for scan patterns (access A, B, C, D, A, B, C, D, ... keeps evicting D)
- Ignores frequency

## LFU (Least Frequently Used)

Remove item used least often.

```
Access pattern: A (5x), B (3x), C (1x), D (1x)
Cache full, new item E arrives
Remove C or D (used once)

Next access: A
  Cache hit (A used 5x, kept)
```

**Pros:**
- Good for skewed workloads (80% of requests are 20% of keys)
- Example: Netflix: 80% of requests for trending 100 videos

**Cons:**
- Expensive to track (need frequency counter for every item)
- Cold items: new item with frequency 0, immediately evicted
- Doesn't adapt to access pattern changes

## ARC (Adaptive Replacement Cache)

Dynamically adjust between LRU and LFU.

```
Maintain two lists:
  - T1: Recently accessed once
  - T2: Recently accessed multiple times

If access pattern is scan (A, B, C, D, A, B, C, D):
  → Favor T2 (items accessed multiple times)
  → Discard from T1 (single-access items)

If access pattern is temporal (A, A, A, then B, B, B):
  → Favor T1 (recent is important)
  → Discard old items from T2
```

**Pros:**
- Adapts to workload
- Balances LRU and LFU
- Used in databases, CDNs

**Cons:**
- Complexity
- Overhead tracking two lists

## Real Examples

**LRU (Redis, Memcached):**
```
Facebook: cache hot posts
  Recent posts likely viewed again
  Old posts: evict them
```

**LFU (Netflix, CDN):**
```
Trending videos: Taylor Swift clip (10M requests/day)
Other video: indie film (10 requests/day)
Cache limited: keep Taylor Swift, evict indie

But: new trending video starts, not in cache (cold)
ARC solves: new video gets into T1, then T2 after multiple accesses
```

**W-TinyLFU (Java ConcurrentHashMap):**
```
Hybrid: mostly LFU, but bias toward recency
Result: good for both patterns
```

## Interview Answers

**Q: "How do you cache 1B users on 100GB cache?"**

A: "Can't fit all 1B. Use LFU: cache hot users (Zipf distribution = 80% traffic from 1% users). Evict cold users. Total: ~100M hot users × 1KB = 100GB. For new users: W-TinyLFU (admit to small window, graduate to main cache after multiple accesses)."

**Q: "Your cache hit rate dropped from 95% to 60%. Why?"**

A: "Access pattern changed. If using LRU and scan started, LRU thrashes (evicts items you'll access next). Solution: switch to ARC or add minimum frequency threshold."
