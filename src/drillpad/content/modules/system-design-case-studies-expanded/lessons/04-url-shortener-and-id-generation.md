# System Design: URL Shortener & Unique ID Generation

## Firm Archetype: Google (goo.gl), Bit.ly, Amazon, Twitter

**Problem:** Generate 100M short URLs with globally unique IDs. Fast lookups, no collisions, URL ordering for analytics, support 1B+ requests/day.

**Why hard:** ID collision at scale, distributed ID generation without centralized DB, ordering for sharding, vanity URLs.

---

## Architecture

```
Client shortens:
  POST /shorten
    ├─ long_url: "https://example.com/very/long/path?q=123"
    ├─ custom: "my-link" (optional)
    └─ ttl: 3600 (optional)

ID Generation Service (Snowflake-style)
  ├─ Timestamp (milliseconds, 41 bits)
  ├─ Worker ID (10 bits, 0-1023 workers)
  ├─ Sequence (12 bits, 0-4095 per ms per worker)
  └─ ID = (ts << 22) | (worker << 12) | sequence
  
  Properties:
    - 64-bit integer (fits in signed long)
    - Sortable by time (earliest first)
    - 1024 workers × 4096 IDs/ms = 4.1M IDs/second
    - No coordination needed (worker ID assigned at startup)

URL Mapping Store
  ├─ Redis: short_id → long_url (1-min TTL, fast)
  ├─ DynamoDB: short_id → {long_url, created_at, ttl, hits, user_id}
  └─ Partitioned by short_id (hash-based sharding)

Reverse Lookup (optional)
  ├─ user_id → [short_ids] (for user dashboard)
  ├─ Stored in DynamoDB GSI or separate index
  └─ Materialized view, eventual consistency OK

Vanity URL Service
  ├─ Check availability: Redis + DynamoDB
  ├─ Reserve for 1 hour (in-flight reservation)
  ├─ Commit on success, release on timeout
```

---

## ID Generation Deep Dive

### Snowflake Design (Twitter)

```
64-bit ID layout:
  [unused (1)] [timestamp (41)] [datacenter (5)] [worker (5)] [sequence (12)]
  
Example:
  Timestamp: 1609459200000 (Jan 1 2021, 41 bits = 69 years max)
  Datacenter: 01 (2 datacenters)
  Worker: 10 (worker 10 in this datacenter)
  Sequence: 234 (234th ID in this millisecond)
  
  ID = 1 << 63 | 1609459200000 << 22 | 1 << 17 | 10 << 12 | 234
```

**Pros:**
- Single RPC per ID (no DB query)
- Ordered by timestamp (useful for time-series queries, analytics)
- No collision risk (each worker has unique ID space per millisecond)
- Distributed: no bottleneck

**Cons:**
- Worker ID management: need service discovery (who is worker 5?)
- Clock skew: if system clock jumps backward, collisions possible (rare)
- Non-sequential within a second (4M IDs/sec, gaps possible)

### UUID Approach (Alternative)

```
UUID v4: 128-bit random
  - Collision risk: negligible (1 in 2^120)
  - No coordination needed
  - NOT ordered (random = poor cache locality)
  - 2x space (128 bits vs 64 bits)
```

**Tradeoff:** UUID simpler, Snowflake faster + ordered.

---

## URL Encoding: Base62 vs Base36

```
Short URL: https://bit.ly/abc123

Base62 encoding (a-z, A-Z, 0-9):
  ID = 123456789
  62^6 = 56 billion IDs (6 chars)
  
  abc123 in base62 = 2 billion+ (lookup)
  
Character set:
  0-9 (10 chars) = base10
  a-z (26 chars) = base36
  a-zA-Z0-9 (62 chars) = base62
  
Why base62 (not base64)?
  - Avoids +/=/ characters (hard in URLs)
  - Avoids case sensitivity issues
  - Shorter URLs
```

---

## Scale Calculation

```
100M short URLs needed
1B requests/day (lookups)

QPS:
  Shorten: 100M/day = 1.16 QPS (low, one-time per URL)
  Lookup: 1B/day = 11,574 QPS (high, repeated)

Peak: 5x lookup = 57,870 QPS

Storage:
  100M URLs × 200 bytes avg = 20 GB (fits in single large DB)
  100M URLs × 500 bytes (with metadata) = 50 GB
  Replication: 3x = 150 GB
  
Sharding:
  Partition by ID (hash-based)
  100 shards × 1M URLs each
  Each shard: 200 MB → fits in cache layer
```

---

## Handling Collisions & Edge Cases

### Collision Prevention

```
Snowflake:
  - Per-millisecond: 4096 IDs per worker
  - 1024 workers = 4.1M IDs/second
  - If >4096 IDs in one ms on one worker:
    → Spin/wait until next millisecond
    → Or: buffer in queue, process next ms
    
UUID:
  - 2^122 possible values
  - Collision probability: sqrt(2^122) ≈ 2^61
  - In practice: negligible for 100M IDs
```

### Clock Skew (Snowflake)

```
System clock jumps backward:
  - Case 1: 10ms jump back
    → Worker uses max_id + 1 (continue forward)
    → Monotonicity preserved within worker
  
  - Case 2: 1 second back (NTP sync)
    → Collision risk: two IDs with same timestamp + worker
    → Mitigation: use max(current_time, last_time)
    → Or: fail request (rare, acceptable)
```

### Vanity URLs (Custom Shorts)

```
Reserve process:
  POST /reserve/my-link (30 sec TTL on reservation)
    ├─ Check: "my-link" available in Redis
    ├─ If yes: add reservation token (UUID)
    └─ Return: {reserved: true, token: uuid, expires_in: 30}
  
  POST /shorten {long_url, custom: "my-link", token: uuid}
    ├─ Check: token still valid
    ├─ Commit: my-link → long_url
    └─ Return: short_url
  
  If not committed in 30s, reservation expires
```

---

## Failure Modes

```
ID generator down:
  → Fallback to UUID v4 (one-time, slower)
  → Or: queue requests, batch when generator recovers
  
DB partition: 
  → Read from cache (Redis) for lookups
  → Write to queue, replay on recovery
  
Clock skew:
  → NTP monitors system clock
  → Large jumps trigger alert
  → Use max(current, last) to prevent reverse IDs
  
Vanity URL collision:
  → Another user claims "my-link" while you reserved it
  → Reservation lock expires after 30s
  → User must retry
```

---

## Code Example (Python, Snowflake)

```python
import time
import threading

class SnowflakeIDGenerator:
    EPOCH = 1609459200000  # Jan 1 2021
    TIMESTAMP_BITS = 41
    WORKER_ID_BITS = 10
    SEQUENCE_BITS = 12
    WORKER_ID_SHIFT = SEQUENCE_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS
    SEQUENCE_MASK = (1 << SEQUENCE_BITS) - 1
    
    def __init__(self, worker_id):
        assert 0 <= worker_id < (1 << WORKER_ID_BITS)
        self.worker_id = worker_id
        self.last_ts = 0
        self.sequence = 0
        self.lock = threading.Lock()
    
    def next_id(self):
        with self.lock:
            ts = int(time.time() * 1000)
            
            if ts < self.last_ts:
                # Clock skew: use last timestamp + 1
                ts = self.last_ts
            
            if ts == self.last_ts:
                # Same millisecond: increment sequence
                self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
                if self.sequence == 0:
                    # Sequence overflow: wait for next ms
                    ts = self._wait_next_ms()
            else:
                # New millisecond: reset sequence
                self.sequence = 0
            
            self.last_ts = ts
            
            # Assemble ID
            id = ((ts - self.EPOCH) << self.TIMESTAMP_SHIFT) | \
                 (self.worker_id << self.WORKER_ID_SHIFT) | \
                 self.sequence
            return id
    
    def _wait_next_ms(self):
        ts = int(time.time() * 1000)
        while ts <= self.last_ts:
            time.sleep(0.001)
            ts = int(time.time() * 1000)
        return ts

class URLShortener:
    BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    def __init__(self, dynamodb, redis, id_gen):
        self.db = dynamodb
        self.cache = redis
        self.id_gen = id_gen
    
    def shorten(self, long_url, custom=None, ttl=None):
        """Create short URL."""
        if custom:
            # Check vanity availability
            if self.cache.get(f"short:{custom}"):
                raise ValueError("Custom URL taken")
            short_id = custom
        else:
            # Generate ID
            numeric_id = self.id_gen.next_id()
            short_id = self._encode_base62(numeric_id)
        
        # Store
        self.db.put_item(
            Item={
                'short_id': short_id,
                'long_url': long_url,
                'created_at': int(time.time()),
                'hits': 0,
                'ttl': ttl
            }
        )
        
        # Cache
        self.cache.set(f"short:{short_id}", long_url, ttl or 86400)
        
        return f"https://bit.ly/{short_id}"
    
    def lookup(self, short_id):
        """Resolve short URL to long URL."""
        # Try cache
        long_url = self.cache.get(f"short:{short_id}")
        if long_url:
            return long_url
        
        # Try DB
        item = self.db.get_item(Key={'short_id': short_id})
        if not item:
            raise KeyError("Short URL not found")
        
        long_url = item['long_url']
        # Update cache
        self.cache.set(f"short:{short_id}", long_url, 3600)
        return long_url
    
    @staticmethod
    def _encode_base62(num):
        if num == 0:
            return "0"
        result = []
        while num > 0:
            result.append(URLShortener.BASE62[num % 62])
            num //= 62
        return ''.join(reversed(result))
```

---

## Interview Checklist

- [ ] Explain Snowflake ID structure (timestamp, worker, sequence)
- [ ] Calculate IDs/second (4.1M with 1024 workers)
- [ ] Handle clock skew (max(current, last_time))
- [ ] Partition strategy (hash-based sharding)
- [ ] Vanity URL reservation (30-sec lock + token)
- [ ] Base62 encoding (why not base64?)
- [ ] Cache strategy (Redis for hot, DB for cold)
- [ ] Failure modes: generator down, clock jump, DB partition

## Common Wrong Answers

- ❌ "Use random UUID" — works but not ordered, wastes space
- ❌ "Central ID service" — bottleneck, single point of failure
- ❌ "No collision handling" — assumes probability alone (need max() for clock skew)
- ❌ "Vanity URLs with no reservation" — race condition if two users claim same URL
- ❌ "Ignore TTL on custom URLs" — vanity URLs live forever, storage grows
