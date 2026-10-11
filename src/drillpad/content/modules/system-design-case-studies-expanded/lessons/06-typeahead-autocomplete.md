# System Design: Typeahead & Autocomplete

## Firm Archetype: Google Search, LinkedIn, Uber, Amazon

**Problem:** User types "fac", suggest "facebook", "facetime", "factors", ranked by popularity. P99 < 100ms, 1M QPS, supporting 1B+ searches/day.

**Why hard:** Latency (P99 < 100ms), ranking by relevance/freshness, real-time updates, handling typos.

---

## Data Structure: Trie (Prefix Tree)

```
Trie for: ["facebook", "facetime", "factors", "fast"]

       [root]
         |
        [f]
         |
        [a]---"fast" (freq: 1000)
       /   \
      [c]   [s]
     / |     |
    [e][t]  [t]
   /|  |     |
  [b][i]    [e]
  |   |      |
  [o] [m]   [r]
  |   |      |
  [o] [e]   [s]
  |        
  [k] "facebook" (freq: 100K)
       "facetime" (freq: 50K)
       "factors" (freq: 5K)

Query "fac":
  1. Traverse: root → f → a → c
  2. At "c" node, collect all descendants: [facebook, facetime, factors]
  3. Sort by frequency: [facebook, facetime, factors]
  4. Return top 5
  
Complexity:
  - Build: O(n * m) where n = words, m = avg length
  - Search: O(k * log k) where k = results, log k = sort
  - Memory: O(n * m) worst case, ~26 bytes/node average
```

---

## Architecture

```
Client types "fac":
  1. Input handler (debounce): wait 100ms, then send
  
  2. HTTPS POST /autocomplete
     {"prefix": "fac", "limit": 5}
     
  3. API Gateway
     ├─ Log query (analytics)
     ├─ Look up in Trie Service
     └─ Return: ["facebook", "facetime", "factors"]
  
  4. Trie Service (in-memory, replicated)
     ├─ RPC to Trie node
     ├─ Trie node: search prefix "fac" in local trie
     └─ Return top 5 results
  
  5. Client renders suggestions
     ├─ User clicks "facebook"
     └─ Emit: search_click {query: "facebook", position: 0}

Analytics:
  ├─ Query log: prefix → click or not
  ├─ Click rate: facebook clicked 80%, facetime 40%, factors 5%
  ├─ Aggregate: daily, push to backend
  └─ Rebuild trie: 1x/day with new frequencies
```

---

## Frequency Ranking

### Naive: Count-based

```
Query log:
  user_123: "facebook" → clicked
  user_456: "facebook" → clicked
  user_789: "facetime" → clicked
  
Count:
  facebook: 2 clicks
  facetime: 1 click
  
Ranking: facebook > facetime
```

**Problem:** Old queries dominate. "javascript" from 5 years ago still ranks high.

### Better: Time-Decay (Exponential)

```
score(query, time) = count * e^(-t / T)

T = time constant (e.g., 30 days)
t = days since query

facebook: count=100, t=1 day
  score = 100 * e^(-1/30) = 96.7

facetime: count=50, t=30 days
  score = 50 * e^(-30/30) = 50/e = 18.4
  
facebook wins (more recent)

Update: daily, exponential decay built in
```

### Better: Trending + Frequency

```
score = (1 - alpha) * frequency + alpha * trend

frequency: all-time clicks
trend: clicks in last 7 days (momentum)
alpha = 0.3 (30% weight on trend)

Example:
  facebook: freq=100K, trend_7day=1000
    score = 0.7 * 100K + 0.3 * 1000 = 70K + 300 = 70.3K
  
  facetime: freq=50K, trend_7day=5000 (trending!)
    score = 0.7 * 50K + 0.3 * 5000 = 35K + 1500 = 36.5K
  
  facebook still wins, but facetime rising
```

---

## Update Pipeline

```
Day 1 (Query log):
  Trie service reads from: Redis + DynamoDB
  Serves stale trie (frequencies from yesterday)
  
  User searches:
    ├─ Emit: search_query {prefix, timestamp, user_id, clicked}
    └─ Write to: Kafka topic (searchlog)

Day 2 (Offline aggregation):
  1. Spark job: read searchlog from Kafka
     ├─ Group by prefix
     ├─ Count clicks
     ├─ Apply time-decay formula
     └─ Aggregate to top 1000 prefixes
  
  2. Output: prefix → [suggestions] (ranked)
     facebook: [
       {text: "facebook", count: 100K, trend: 1000},
       {text: "facetime", count: 50K, trend: 5000},
       ...
     ]
  
  3. Store in: DynamoDB + Redis (L1 cache)
  
  4. Trie service:
     ├─ Check Redis for update signal
     ├─ Load new top-1000 from DynamoDB
     ├─ Rebuild trie in memory (fast, seconds)
     └─ Switch: old trie → new trie (atomic)

Day 3:
  Trie service serves updated results
```

---

## Handling Typos & Fuzzy Matching

```
User types: "favebook" (typo)
  1. Exact match in trie: no results
  2. Fuzzy match (edit distance <= 1):
     ├─ Substitution: "f" → "f", "a" → "a", "v" → "c", ...
     ├─ Check: "facebo..." exists? → "facebook"
     ├─ Distance: 1 (one char different)
  3. Return: ["facebook", "facetime"] (edit distance <= 1)
  
  Complexity: O(k * 26) where k = trie size
    → Too slow for real-time

Better: Spell corrector (pre-built)
  1. Precompute: common misspellings
  2. "favebook" → "facebook" (lookup in map)
  3. Return suggestions for corrected query
  
  Build from: search logs (typos that got clicked through)
  
Phonetic matching (sounds like):
  "phacebook" → "facebook"
  Use: metaphone/soundex algorithm
```

---

## Caching Strategy

### L1: Client-side

```
Browser cache:
  GET /autocomplete?prefix=fac
  Response: ["facebook", "facetime", "factors"]
  Cache: 1 hour (in-memory)
  
User types "fac" again:
  → Return from cache (instant)
  
Problem: outdated (if trending changes)
Solution: versioning + invalidation
  Response header: X-Trie-Version: 123
  If new version available, invalidate
```

### L2: CDN (Edge)

```
Cache autocomplete responses:
  GET /autocomplete/facebook → "facebook", "facetime", ...
  CDN caches: 15 minutes
  
Pros:
  - P50: 10ms (edge location)
  - Cheap (no computation)
  
Cons:
  - Stale (15 min delay on updates)
  - Large response size (all 5 suggestions)
  
Trade-off: acceptable for trending
```

### L3: Trie Service (in-memory)

```
Trie stored in: RAM
  Size: 1B unique prefixes × 100 bytes = 100 GB
  
Too large for single machine
  → Shard by first 2 chars
  → "fa" shard: 1 billion / 26^2 = 1.5M prefixes
  → Size: 1.5M * 100 bytes = 150 MB (fits)
  
Replicate: 3x for redundancy
  fa_shard_1, fa_shard_2, fa_shard_3
```

---

## Scale Calculation

```
1B DAU
Active daily: 50% = 500M
Searches/user/day: 5
QPS: 500M * 5 / 86400 = 28,935 QPS
Peak: 5x = 144,675 QPS

Unique prefixes:
  Each search generates: avg 5 characters (user types to first suggestion)
  5 chars × 28,935 QPS = 144,675 queries/day
  Unique: 1B / 28,935 = 34,562 unique prefixes
  
  Real: 1-2B unique prefixes (typos, variations)

Trie size:
  1B prefixes × 100 bytes = 100 GB
  → Shard by first 2-3 chars (26^2 = 676 shards)
  → Each shard: 150 MB (fits in RAM)

Sharding:
  prefix "fac" → hash("fa") % 676 = shard 42
  Request routed to: trie_service_42
```

---

## Failure Modes

```
Trie service down (shard 42):
  → Client: fallback to typing.com or previous cache
  → No autocomplete for "fa*" queries
  → Replicate: 3x, failover to replica
  
Stale trie (update lag):
  → Offline job failed, new frequencies not loaded
  → Trie serves yesterday's results
  → Impact: trending misses for 1 day
  → Mitigation: daily alerts, manual rebuild

Large update (trie rebuild):
  → Spark job outputs 10 GB file
  → Load into service: takes 30 seconds
  → During load: old trie still serves (no downtime)
  → Switch: atomic pointer swap (new trie → old)
```

---

## Code Example (Python, Trie)

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.suggestions = []  # List[(word, frequency)]

class AutocompleteService:
    def __init__(self):
        self.root = TrieNode()
        self.trie = {}  # shard_id -> Trie
        self.cache = {}  # prefix -> suggestions (local cache)
    
    def build_trie(self, words_and_freqs):
        """Build trie from (word, frequency) list."""
        for word, freq in words_and_freqs:
            node = self.root
            for char in word:
                if char not in node.children:
                    node.children[char] = TrieNode()
                node = node.children[char]
                
                # Store top-5 at each node
                node.suggestions.append((word, freq))
                node.suggestions.sort(key=lambda x: x[1], reverse=True)
                node.suggestions = node.suggestions[:5]
    
    def search(self, prefix, limit=5):
        """Find suggestions for prefix."""
        # Check cache
        if prefix in self.cache:
            return self.cache[prefix]
        
        # Traverse trie
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []  # No match
            node = node.children[char]
        
        # At prefix node, suggestions are ranked
        results = [word for word, freq in node.suggestions[:limit]]
        
        # Cache
        self.cache[prefix] = results
        return results
    
    def update_from_logs(self, search_logs):
        """Update frequencies from search logs."""
        freq_map = {}
        
        for log in search_logs:
            prefix = log['prefix']
            if log['clicked']:
                freq_map[prefix] = freq_map.get(prefix, 0) + 1
        
        # Rebuild trie
        self.root = TrieNode()
        self.cache.clear()
        
        words = sorted(
            freq_map.items(),
            key=lambda x: x[1],
            reverse=True
        )
        self.build_trie(words)

# Fuzzy matching
def edit_distance(s1, s2):
    """Compute Levenshtein distance."""
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1+1], distances_[-1])))
        distances = distances_
    
    return distances[-1]

def fuzzy_search(trie_service, prefix, max_distance=1):
    """Find suggestions with typo tolerance."""
    # Check all words with edit distance <= max_distance
    candidates = []
    
    def dfs(node, word, dist):
        if dist < 0:
            return
        
        if node.suggestions and dist == 0:
            candidates.extend(node.suggestions)
        
        for char, child in node.children.items():
            new_dist = dist - (1 if char != word[len(word)-dist] else 0)
            dfs(child, word, new_dist)
    
    dfs(trie_service.root, prefix, max_distance)
    return candidates
```

---

## Interview Checklist

- [ ] Explain trie structure (prefix matching, space-time tradeoff)
- [ ] Frequency ranking (count, time-decay, trending)
- [ ] Update pipeline (offline Spark job, atomic switch)
- [ ] Sharding strategy (hash-based, ~150 MB per shard)
- [ ] Caching layers (client, CDN, trie service)
- [ ] Typo handling (fuzzy matching, spell correction)
- [ ] Scale calculation (1B prefixes, 144K QPS peak)
- [ ] Failure modes (shard down, stale trie)

## Common Wrong Answers

- ❌ "Store all results in a single database query" — 144K QPS, DB can't handle
- ❌ "Rank by frequency alone" — old queries never age out
- ❌ "Update trie in real-time" — too expensive, rebuild takes minutes
- ❌ "No sharding" — 100 GB in one machine's RAM
- ❌ "Return all suggestions" — response too large, latency misses
- ❌ "Ignore typos" — 20% of queries are misspelled
