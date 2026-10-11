# Fault Tolerance: Circuit Breakers & Retries (Fail Fast, Exponential Backoff)

## Typical Contexts: payments, cloud platforms, and trading systems

**Problem:** Service A calls Service B. Service B times out or crashes. What does A do?

- **Bad:** Retry immediately 10x → overwhelms B, cascades failure
- **Better:** Exponential backoff (wait 1s, 2s, 4s...) → slower recovery
- **Best:** Circuit breaker (fail fast after N failures, stop retrying) → prevent cascade

**Why hard:** Must balance reliability (retry) with cascading failure prevention (stop retrying).

---

## The Cascade Problem

```
Without circuit breaker:
  Service A: call B → timeout (1s)
  Service A: retry → timeout (1s)
  Service A: retry → timeout (1s)
  Service A: thread pool saturated (blocking on B)
  Service A: can't serve its own requests → cascades up

With circuit breaker:
  Service A: call B → timeout (1s) [counter=1]
  Service A: retry → timeout (1s) [counter=2]
  Service A: call B → CIRCUIT OPEN (no call) [return error immediately]
  Service A: threads freed, serves other requests
  Service B: has 30 seconds to recover
  Service A: half-open → test 1 request → if success, reset
```

---

## Circuit Breaker States

```
CLOSED (normal):
  ├─ Requests pass through
  ├─ Success: counter resets
  └─ Failure: counter++
      └─ If counter >= threshold (5): OPEN

OPEN (stop trying):
  ├─ Requests rejected immediately
  ├─ Return error without calling downstream
  └─ After timeout (30s): HALF_OPEN

HALF_OPEN (test recovery):
  ├─ Allow 1 request through
  ├─ If success: CLOSED (reset counter)
  └─ If failure: OPEN (restart timeout)
```

---

## Real Example: Your Payment Adapter

**Claim:** "circuit breakers, idempotent retries, async callbacks, cutting Japanese seller onboarding from 6 days to 5 minutes"

**Root cause:** Payment provider was slow. Payment Adapter kept retrying synchronously, blocking sellers.

**Solution:**
1. **Async** - don't block seller on payment result
2. **Circuit breaker** - after 5 failures, stop calling provider for 30s
3. **Exponential backoff** - retry with 1s, 2s, 4s, 8s delays (with jitter)
4. **Idempotency** - safe to retry (idempotency key)

**Result:** Seller sees "accepted" in 5 min (vs 6 days waiting for provider to recover)

---

## Implementation: Python with Exponential Backoff + Jitter

```python
import time
import random
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30, name="CircuitBreaker"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
    
    def call(self, func, *args, **kwargs):
        """Execute func with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                print(f"[{self.name}] HALF_OPEN: attempting reset")
            else:
                raise Exception(f"[{self.name}] Circuit OPEN (will retry in {self._seconds_until_retry()}s)")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Record success, potentially close circuit."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            print(f"[{self.name}] CLOSED: recovery successful")
    
    def _on_failure(self):
        """Record failure, potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"[{self.name}] OPEN: threshold ({self.failure_threshold}) reached")
    
    def _should_attempt_reset(self):
        """Check if enough time has passed to try HALF_OPEN."""
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _seconds_until_retry(self):
        """Seconds until next retry attempt."""
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return max(0, int(self.recovery_timeout - elapsed))

class ExponentialBackoffRetry:
    def __init__(self, max_retries=5, initial_delay=1, max_delay=60, jitter=True):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter = jitter
    
    def call(self, func, *args, **kwargs):
        """Execute func with exponential backoff retry."""
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                
                delay = min(self.initial_delay * (2 ** attempt), self.max_delay)
                if self.jitter:
                    delay *= random.uniform(0.5, 1.5)
                
                print(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)

# Real usage pattern: payment adapter
class PaymentAdapter:
    def __init__(self):
        self.breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="PaymentProvider")
        self.retry = ExponentialBackoffRetry(max_retries=4, initial_delay=1, max_delay=32)
    
    def charge(self, seller_id, amount, idempotency_key):
        """Charge with circuit breaker + retry."""
        try:
            return self.retry.call(
                self.breaker.call,
                self._charge_with_provider,
                seller_id, amount, idempotency_key
            )
        except Exception as e:
            print(f"Charge failed: {e}")
            # Queue for async retry
            self._queue_async_retry(seller_id, amount, idempotency_key)
            raise
    
    def _charge_with_provider(self, seller_id, amount, idempotency_key):
        """Call external payment provider."""
        # Simulate provider call
        if random.random() < 0.6:  # 60% failure rate for demo
            raise Exception("Provider timeout")
        return {"charge_id": f"ch_{idempotency_key}", "status": "success"}
    
    def _queue_async_retry(self, seller_id, amount, idempotency_key):
        """Queue for SQS async retry."""
        print(f"Queued async retry: {seller_id}, {amount}, {idempotency_key}")
```

---

## Design Decisions

**Why circuit breaker instead of infinite retries?**
- Infinite retries: overwhelm downstream, cascade failure
- Circuit breaker: fail fast, let downstream recover

**Why exponential backoff with jitter?**
- Linear backoff (1s, 2s, 3s): too fast, thundering herd
- Exponential (1s, 2s, 4s, 8s): good, but synchronized retries
- Jitter (1s * [0.5, 1.5]): stagger retries, avoid thundering herd

**Why HALF_OPEN state?**
- Without it: circuit stays OPEN forever (no recovery test)
- With it: periodically test recovery, close if successful

**Why idempotency key with retry?**
- Without: retry might double-charge
- With: retry is safe, can retry 100x

---

## Q&A

**Recall 1:** Why does circuit breaker prevent cascade?

*Must-say:*
- Circuit breaker fails fast (no waiting, no threads blocked)
- Threads are freed to serve other requests
- Downstream gets breathing room to recover
- Once recovered, HALF_OPEN resets circuit

**Probe 1:** Failure threshold = 3. After 3 failures, circuit opens. Then downstream recovers. When does circuit close?

*Expected:*
- Circuit stays OPEN for recovery_timeout (30s)
- After 30s: circuit → HALF_OPEN
- Next request: test with 1 request
- If success: CLOSED, failure_count resets
- If fail: OPEN again, restart 30s timer

**Numeric 1:** Max retries = 4. Delays: 1s, 2s, 4s, 8s (no jitter). Total wait time before giving up?

*Working:*
- Attempt 0: immediate
- Fail → wait 1s
- Attempt 1: immediate
- Fail → wait 2s
- Attempt 2: immediate
- Fail → wait 4s
- Attempt 3: immediate
- Fail → wait 8s
- Attempt 4: immediate
- Total wait: 1 + 2 + 4 + 8 = 15 seconds

**Probe 2:** You have jitter=True. Delay = 2s * random[0.5, 1.5]. What's the jitter range?

*Expected:*
- Min: 2s * 0.5 = 1s
- Max: 2s * 1.5 = 3s
- Staggered over [1s, 3s] range, avoids thundering herd

---

## Questions for the Interviewer

- What's your failure threshold? (3, 5, 10?)
- How long is recovery_timeout? (30s, 60s?)
- Do you use jitter? (avoid thundering herd?)
- How do you test circuit breaker behavior? (chaos engineering?)
- Have you had cascade failures before? (what caused them?)

