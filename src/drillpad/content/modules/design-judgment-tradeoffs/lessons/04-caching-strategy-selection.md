# Design Judgment: Caching Strategy (Pick LRU/LFU/ARC from Data)

## The Problem: You Can't Have It All

```
LRU: Good for temporal locality (Spotify: recent songs)
LFU: Good for skewed popularity (Netflix: top 100 videos)
ARC: Good for both (adapts to workload)

But:
- LRU: Fails on scan patterns (access A,B,C,D,A,B,C,D...)
- LFU: Cold items die immediately (new video never cached)
- ARC: Higher complexity, more overhead

Wrong choice: Hit rate 80% instead of 95% = 6.25x more requests to origin
Right choice: Hit rate 95%, same cost
```

## Decision Framework: Look at Your Data

### Pattern 1: Temporal Locality (Recent Items Popular)

**Spotify: User's recent play history**

```
Data pattern:
  - User listens to Song A (recent)
  - Probability of repeat in next 1 hour: 60%
  - Probability of repeat in next 24 hours: 30%
  - Probability of repeat in next 30 days: 5%

Decision: LRU
  - Keep recent songs in cache
  - Evict old songs (won't be played again)
  - Hit rate: 85% (good for this pattern)

Metrics:
  - Cache size: 1GB (10k songs × 100KB)
  - Hit rate: 85%
  - Miss rate: 15% (disk access)
```

**Why not LFU?**
```
LFU would track:
  - Song A: 150 plays
  - Song B: 130 plays
  - Song C: 5 plays
  
Evict Song C (lowest frequency)
New song D added: 0 plays
If user wants Song D: cache miss (too new to have high frequency)

Result: New songs never cached, hit rate drops to 60%
```

### Pattern 2: Skewed Popularity (Zipf Distribution)

**Netflix: Top 100 videos get 80% of traffic**

```
Data pattern:
  - Top 100 videos: 80% of requests
  - Next 1000 videos: 15% of requests
  - Long tail (1M+ videos): 5% of requests
  
Decision: LFU
  - Frequency counter for each video
  - Cache top 100 (high frequency)
  - Evict when space needed (remove lowest frequency)
  - Hit rate: 92% (skewed workload)

Example:
  - Avatar: 10M views/month
  - Indie film: 10 views/month
  - LFU caches Avatar, not indie film
  - Hit rate: 92%
```

**Why not LRU?**
```
LRU with access pattern:
  1. Avatar watched (recent)
  2. Indie film watched (recent, evicts old Avatar access)
  3. Avatar watched again (cache miss, even though popular)
  
With enough users watching indie films:
  - Avatar is evicted frequently
  - Hit rate drops to 60%
```

### Pattern 3: Mixed (Temporal + Skewed)

**Real-world example: Reddit's front page**

```
Data pattern:
  - New posts: Get upvotes fast, decay
  - Popular posts (>10k upvotes): Stable for days
  - Dead posts: No traffic
  
Decision: ARC (Adaptive Replacement Cache)
  - Tracks "recently accessed once" (T1)
  - Tracks "recently accessed multiple times" (T2)
  - Adapts based on miss pattern
  
Example:
  - New viral post: T1 → T2 after 2 accesses
  - Old post getting traffic: stays in T2
  - Indie video: T1 only, evicted if space needed
  
  Hit rate: 93% (adapts to both patterns)
```

## Measuring Pattern: The Data Investigation

**Before choosing, ask:**

```
Question 1: Is there a "hot set" (80/20)?
  - Yes → LFU likely better
  - No → LRU likely better
  - Mixed → ARC

Question 2: Do access patterns change over time?
  - Yes (temporal shift) → LRU/ARC
  - No (stable distribution) → LFU
  
Question 3: Are new items valuable?
  - Yes (new songs, new videos) → LRU, not LFU
  - No (old data is best) → LFU
```

## Real Interview Scenarios

### Scenario 1: Designing YouTube Cache

**Q: "Design a cache for YouTube videos. How do you choose eviction policy?"**

Weak answer:
```
"Use LRU. Recent videos are more likely to be watched."
(❌ Wrong: New videos aren't "recent" until first access; 
    YouTube's hit rate would drop when new viral video drops)
```

Strong answer:
```
"YouTube has two patterns:
  1. Viral trend (new video, gets 1M views/day)
  2. Evergreen content (old video, stable 100k views/day)

Data analysis:
  - Top 100 videos: 60% of traffic
  - Next 10k videos: 35% of traffic
  - Tail: 5%
  
This is SKEWED (Zipfian), so LFU is better.

But also: New videos become popular (temporal).
So use ARC: Start videos in T1 (recent), graduate to T2 if popular.

Expected hit rate: 92% (vs 80% with pure LRU)"
```

Why strong:
- Analyzed the actual data pattern
- Justified the choice (Zipfian distribution)
- Mentioned adaptation for new content
- Named the expected improvement

### Scenario 2: Designing Cache for User Sessions

**Q: "Cache user sessions for 100M users. How?"**

Weak answer:
```
"LRU: Most active sessions are recent."
(❌ Wrong: 50M users inactive, 50M active; 
    50% of cache filled with dead sessions)
```

Strong answer:
```
"User sessions have bimodal distribution:
  - Active users (2% of 100M): Highly accessed
  - Inactive users (98% of 100M): Never accessed again
  
If I use LRU:
  - Cache fills with inactive users (low hit rate)
  
Solution: LFU with min-frequency threshold
  - Track access count
  - Only cache sessions with ≥ 5 accesses in last hour
  - Evict sessions with 0 accesses (never come back)
  
Result:
  - Cache: 2M active users × 10KB = 20GB
  - Hit rate: 98% (only active users)
  - vs LRU hit rate: 50% (mix of active/inactive)
  
Cost savings: 6.25x fewer cache misses"
```

Why strong:
- Identified bimodal distribution
- Explained LRU failure
- Proposed frequency threshold (hybrid)
- Quantified improvement

## Hybrid Strategies (Don't Pick Just One)

### LFU with Time Decay

```
Spotify's approach (estimated):
  - Frequency counter: play_count
  - Time decay: divide by (1 + age_in_days)
  - Score = play_count / (1 + age_in_days)
  
Recent popular song (40 plays, 1 day old):
  Score = 40 / (1 + 1) = 20
  
Old but very popular song (400 plays, 10 days old):
  Score = 400 / (1 + 10) = 36
  
Result: Both cached (new + popular), old unpopular evicted
Hit rate: 88% (temporal + skewed)
```

### LRU with Frequency Threshold

```
Redis's approach:
  - Keep LRU (simple)
  - But only evict items with low frequency
  - Items with high frequency: protected from eviction
  
If item accessed 5+ times: Don't evict (keep it)
If item accessed 1x: Can evict (LRU order)

Result: Popular items protected, temporal ordering respected
Hit rate: 85% (hybrid)
```

## Interview Decision Checklist

**When asked "which cache eviction policy?":**

- [ ] Ask: "What's the workload?"
  - Temporal (recent = popular) → LRU
  - Skewed (some items >> popular) → LFU
  - Mixed → ARC or hybrid
  
- [ ] Ask: "What's the consequence of miss?"
  - Expensive (disk I/O) → Choose best hit rate (ARC)
  - Cheap (in-memory fallback) → Choose simple (LRU)
  
- [ ] Ask: "Do new items matter?"
  - Yes (videos, songs, posts) → Avoid pure LFU
  - No (static database) → Pure LFU fine

- [ ] Calculate expected hit rates
  - LRU: 85% for temporal
  - LFU: 92% for skewed
  - ARC: 93% for mixed

- [ ] Name the tradeoff
  - LRU: Simple, low overhead
  - LFU: Better hit rate, higher overhead
  - ARC: Best hit rate, highest overhead (complexity cost)

## Red Flags vs Green Flags

**🚩 Red flags you're wrong:**

1. "LRU for everything" (YouTube would be 60% hit rate)
2. "LFU for everything" (new items never cached)
3. No mention of data pattern (how do you know which to pick?)
4. No measurement (hit rate estimation)

**✅ Green flags you're right:**

1. Analyzed actual data distribution (Zipfian? temporal? mixed?)
2. Explained why one policy beats others for this pattern
3. Named expected hit rate improvement
4. Mentioned overhead/cost tradeoff
5. Suggested hybrid if workload is mixed

