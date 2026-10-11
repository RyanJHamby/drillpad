# Rate Limiting: Token Bucket, Sliding Window, Load Shedding

## Typical Contexts: payments, cloud platforms, and trading systems

**Problem:** API receives 10K req/sec, but backend can only handle 1K req/sec. What do you do?

- **Bad:** Queue everything → system backs up, latency skyrockets, users timeout
- **Better:** Drop oldest requests → some users get dropped, but others are served
- **Best:** Rate limit → reject requests gracefully when capacity is exceeded

**Why hard:** Must balance fairness (don't starve anyone) with throughput (handle spike load).

---

## Approaches

```
No rate limiting:
  10K req/sec → 1K capacity → 9K queued
  Queue grows forever → latency goes to ∞
  Users timeout after 30s → cascade failure
  
Reject requests (queue-drop):
  10K req/sec → 1K capacity → drop 9K
  Latency: 1ms (those that made it)
  Fairness: random drop
  
Rate limit (token bucket):
  10K req/sec → 1K capacity → allow 1K, queue 9K
  Latency: ~1s (wait in queue)
  Fairness: FIFO + priority
  
Load shedding (circuit breaker + rate limit):
  10K req/sec → 1K capacity → allow 1K, reject 9K immediately
  Latency: 1ms (those that made it)
  Fairness: reject non-critical requests first
```

---

## Algorithm 1: Token Bucket

```
Bucket capacity: 1000 tokens
Refill rate: 100 tokens/sec

Request comes in:
  ├─ Needs 10 tokens
  ├─ Bucket has 1000 tokens: grant, remove 10 tokens
  ├─ Bucket has 50 tokens: grant, remove 10 tokens
  └─ Bucket has 5 tokens: DENY (not enough)

Refill (runs every 10ms):
  Current: 50 tokens
  Elapsed: 10ms = 0.01s
  Refill: 100 tokens/sec * 0.01s = 1 token
  New: 51 tokens
```

**Pros:** Simple, fair, allows bursts (bucket can accumulate)
**Cons:** Refill thread overhead

---

## Algorithm 2: Sliding Window

```
Window: last 60 seconds

Request at t=10s:
  Requests in [t-60s, t] = 100
  Capacity: 1000
  Allow
  
Request at t=60.5s:
  Requests in [t-60s, t] = 50
  Capacity: 1000
  Allow
  
Request at t=61s:
  Requests in [t-60s, t] = 1050
  Capacity: 1000
  DENY (exceeded)
```

**Pros:** Exact tracking, no refill needed
**Cons:** Memory (store all request timestamps)

---

## Algorithm 3: Leaky Bucket (Queue-Based)

```
Queue capacity: 1000 requests
Drain rate: 100 req/sec

Request comes in:
  ├─ Queue has 500 requests: add to queue, wait
  ├─ Queue has 950 requests: add to queue, wait ~5s
  └─ Queue has 1000 requests: DENY (full)

Drain (runs 100 times/sec):
  Pop 1 request from queue
  Process
  Send response
```

**Pros:** Smooth processing, no jitter
**Cons:** Latency increases as queue fills

---

## Implementation: Python Token Bucket

```python
import time
import threading
from collections import defaultdict

class TokenBucket:
    def __init__(self, capacity, refill_rate):
        """
        capacity: max tokens in bucket
        refill_rate: tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens=1):
        """Try to acquire tokens. Returns True if granted."""
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        """Top up bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

class PerUserRateLimiter:
    """Rate limit per user ID."""
    def __init__(self, requests_per_second=10):
        self.buckets = defaultdict(lambda: TokenBucket(capacity=requests_per_second, refill_rate=requests_per_second))
    
    def allow(self, user_id):
        """Returns True if request is allowed."""
        bucket = self.buckets[user_id]
        return bucket.acquire(tokens=1)

# Real usage: API endpoint
class APIEndpoint:
    def __init__(self):
        self.limiter = PerUserRateLimiter(requests_per_second=100)
    
    def handle_request(self, user_id, request_data):
        if not self.limiter.allow(user_id):
            return {"error": "rate_limit_exceeded", "status": 429}
        
        # Process request
        return {"status": 200, "data": f"processed for {user_id}"}
```

---

## Implementation: Python Sliding Window (Memory-Efficient)

```python
from collections import deque
import time

class SlidingWindowCounter:
    def __init__(self, window_seconds=60, capacity=1000):
        self.window_seconds = window_seconds
        self.capacity = capacity
        self.timestamps = deque()  # [t1, t2, ..., tn]
    
    def allow(self, user_id):
        """Returns True if request is allowed."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Remove old timestamps outside window
        while self.timestamps and self.timestamps[0] < window_start:
            self.timestamps.popleft()
        
        # Check capacity
        if len(self.timestamps) < self.capacity:
            self.timestamps.append(now)
            return True
        return False

# Note: For per-user tracking, use defaultdict(SlidingWindowCounter)
```

---

## Load Shedding: Priority-Based

```python
class LoadShedding:
    def __init__(self, priority_thresholds=None):
        """
        priority_thresholds: {
            'critical': 0.8,     # allow 80% capacity
            'normal': 0.5,       # allow 50% capacity
            'background': 0.2    # allow 20% capacity
        }
        """
        self.priority_thresholds = priority_thresholds or {
            'critical': 0.9,
            'normal': 0.5,
            'background': 0.2
        }
        self.current_load = 0
        self.capacity = 1000
    
    def allow(self, priority='normal'):
        """Returns True if request should be allowed."""
        threshold = self.priority_thresholds.get(priority, 0.5)
        load_percent = self.current_load / self.capacity
        
        if load_percent > threshold:
            return False  # Shed this request
        
        self.current_load += 1
        return True
    
    def finish_request(self):
        """Call when request finishes."""
        self.current_load = max(0, self.current_load - 1)
```

---

## Worked Example: Trading Order Book

**Scenario:** Order book receives 1M orders/sec from market feeds. Matching engine can only process 800K orders/sec.

**Solution:** Rate limit by source (market feed):
- **Exchange A** (critical): allow 600K orders/sec
- **Exchange B** (normal): allow 200K orders/sec
- **Exchange C** (background): allow 0 until load drops

```python
class OrderBookRateLimiter:
    def __init__(self):
        self.limiters = {
            'EXCH_A': TokenBucket(capacity=600000, refill_rate=600000/60),  # 600K/min
            'EXCH_B': TokenBucket(capacity=200000, refill_rate=200000/60),
            'EXCH_C': TokenBucket(capacity=0, refill_rate=0)  # blocked
        }
    
    def accept_order(self, exchange, order):
        if self.limiters[exchange].acquire(tokens=1):
            return {"status": "accepted"}
        return {"status": "rejected"}
```

---

## Design Decisions

**Why token bucket over sliding window?**
- Token bucket: simpler, allows bursts
- Sliding window: exact but needs per-request tracking
- Choose bucket for APIs, window for batch systems

**Why rate limit per user instead of global?**
- Global: one user can starve others
- Per-user: fairness, but more state

**Why load shedding?**
- Better than queueing (no latency increase)
- Prioritizes critical requests
- Transparent to client (fast reject)

**Why jitter in token bucket?**
- Without: all clients refill at same time → thundering herd
- With: spread refills → smoother load

---

## Q&A

**Recall 1:** Token bucket has capacity 1000, refill 100 tokens/sec. Can I burst 2000 requests in 1 second?

*Must-say:*
- Bucket starts with 1000 tokens (max)
- First 1000 requests: allowed immediately
- Next 1000 requests: wait 10 seconds (to refill)
- So no, can't do 2000 in 1s, only 1000 in 1s

**Probe 1:** You use sliding window with window=60s, capacity=1000. Request 1 comes at t=0, request 1001 at t=59.9s, request 1002 at t=60.1s. What happens?

*Expected:*
- t=0: request 1 allowed (count=1)
- t=59.9s: request 1001 allowed (count=1001, over limit but within window)
- t=60.1s: window slides, request 1 dropped (outside [0s, 60.1s] window)
- Request 1002: allowed (count=1001 - 1 + 1 = 1001, still over)

**Numeric 1:** API limit: 100 req/sec per user. I send 50 reqs/sec. In 10 seconds, how many requests can I burst?

*Working:*
- Token bucket: capacity=100, refill=100/sec
- At t=0: 100 tokens available, 100 allowed (burst)
- Then: generating 100 tokens/sec
- In 10s: 100 * 10 = 1000 tokens generated
- Total by t=10: 100 (initial) + 1000 (generated) = 1100 tokens
- But I only used 50*10 = 500 tokens
- So yes, can burst up to 100 tokens at any time

---

## Questions for the Interviewer

- Do you rate limit per user, per endpoint, or globally?
- What's your refill rate and bucket capacity? (tuned how?)
- Do you use token bucket or sliding window?
- How do you handle rate limit exceeded? (queue, reject, delay?)
- Do you implement load shedding? (prioritize critical requests?)
- Have you had rate limit bugs? (what caused them?)

