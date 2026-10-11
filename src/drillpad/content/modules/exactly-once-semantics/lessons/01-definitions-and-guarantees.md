# Delivery Guarantees: At-Most-Once, At-Least-Once, Exactly-Once

## First Principle: Three Delivery Modes

When you send a message, one of three things can happen:

```
AT-MOST-ONCE (≤1 delivery):
  Send message → network timeout → don't retry
  Result: Message lost (0 deliveries)
  Problem: Money not charged, order not created
  Use case: Telemetry, analytics (ok to lose some data)

AT-LEAST-ONCE (≥1 delivery):
  Send message → network timeout → retry automatically
  Result: Message delivered 1+ times (might be duplicate)
  Problem: Money charged twice, order created twice
  Use case: Messaging systems (retry until success)

EXACTLY-ONCE (exactly 1 delivery):
  Send message → retry with idempotency key
  Result: Message processed exactly once (deduplicated on receiver)
  Problem: None (safe for payments)
  Use case: Payment systems, financial transactions
```

---

## Why Exactly-Once is Hard

```
Simple approach (doesn't work):
  Client sends: POST /charge?amount=100
  Server receives, charges $100
  Server responds: "OK, charged $100"
  
  If response lost:
    Client thinks: "charge failed"
    Client retries: POST /charge?amount=100
    Server receives, charges another $100
    Result: $200 charged (duplicate)

Correct approach (idempotency):
  Client sends: POST /charge?amount=100&idempotency_key=abc123
  Server:
    1. Check: has this idempotency_key been seen? (DynamoDB)
    2. If yes: return previous result (don't charge again)
    3. If no: charge $100, store (idempotency_key, result) in DynamoDB
  
  If response lost:
    Client retries: POST /charge?amount=100&idempotency_key=abc123
    Server checks: idempotency_key=abc123 already exists
    Server returns: previous result (amount_charged: $100)
    Result: $100 charged (correct)
```

---

## Guarantees Hierarchy

```
At-Most-Once:
  ├─ No retry
  ├─ Fast (one shot)
  └─ Problem: data loss

At-Least-Once:
  ├─ Automatic retry
  ├─ Reliable delivery
  └─ Problem: duplicates
  
Exactly-Once:
  ├─ Retry + deduplication
  ├─ Idempotency key + storage
  └─ Problem: complexity + latency (check before processing)
```

**Cost per guarantee:**
- At-most-once: 1 operation
- At-least-once: retry logic + network
- Exactly-once: idempotency check + storage write (slower)

---

## Implementation Pattern

```python
class PaymentSystem:
    def charge(self, user_id, amount, idempotency_key):
        """
        Exactly-once charge using idempotency key.
        """
        # Step 1: Check if we've already processed this
        previous_result = self.idempotency_store.get(idempotency_key)
        if previous_result:
            # Already processed, return cached result
            return previous_result
        
        # Step 2: Process the charge
        try:
            charge_id = self.payment_provider.charge(user_id, amount)
            result = {
                "status": "success",
                "charge_id": charge_id,
                "amount": amount
            }
        except Exception as e:
            result = {
                "status": "failed",
                "error": str(e)
            }
        
        # Step 3: Store result (atomic with idempotency key)
        # This is critical: if this fails, retry will re-process
        self.idempotency_store.put(idempotency_key, result)
        
        return result
```

---

## Idempotency Key Storage

**Requirements:**
- Fast lookup: O(1), milliseconds
- Durable: survives crashes
- Atomic: can't lose result after charging

**Typical implementation:** DynamoDB (or any key-value store)

```
Table: Idempotency
┌──────────────────────────────────┬──────────────────────┐
│ idempotency_key (PK)             │ result               │
├──────────────────────────────────┼──────────────────────┤
│ abc123                           │ {success, id:12345}  │
│ def456                           │ {failed, error:...}  │
│ ghi789                           │ {success, id:12346}  │
└──────────────────────────────────┴──────────────────────┘

On retry with same key:
  1. Query by idempotency_key (fast, index on PK)
  2. If found: return result immediately
  3. If not found: process and insert
```

**Gotcha: Concurrent requests with same key**

```
Request 1: idempotency_key=abc123 → check DynamoDB (not found) → charge $100
Request 2: idempotency_key=abc123 → check DynamoDB (not found yet!) → charge $100

Problem: Both requests process before either stores result

Solution: Atomic compare-and-set
  1. Try to insert (idempotency_key, IN_PROGRESS) atomically
  2. If insert fails (key exists), fetch existing result
  3. If insert succeeds, do work, update to COMPLETED
```

---

## Story Card: Payment Adapter (Your Resume)

**Resume claim:** "Payment Adapter Service (idempotent retries, async callbacks), cutting Japanese seller onboarding from 6 days to 5 minutes"

**Setup:** AWS Marketplace, sellers submit orders via API.

**Problem:** Without idempotency
- Seller submits order, gets timeout
- Seller retries (browser refresh)
- Both requests charge $X
- Seller sees two charges
- Support tickets, reconciliation required

**Solution:** Idempotency keys
- Client generates idempotency_key = UUID (per order submission)
- Server:
  1. Check: has this key been processed? (DynamoDB)
  2. If yes: return cached response
  3. If no: charge, async callback to seller
- Seller sees immediate confirmation, won't retry
- Even if retry: idempotency key prevents double-charge

**Implementation:**
```python
# Client-side
idempotency_key = str(uuid.uuid4())
response = api.submit_order(
    seller_id=123,
    amount=100,
    idempotency_key=idempotency_key
)

# Server-side
previous = payment_adapter.idempotency_store.get(idempotency_key)
if previous:
    return previous  # Already processed
else:
    result = payment_provider.charge(seller_id, amount)
    payment_adapter.idempotency_store.put(idempotency_key, result)
    payment_adapter.async_notify_seller(seller_id, result)
    return result
```

**Result:**
- Seller doesn't see "error, please retry"
- No manual reconciliation
- Onboarding time: 6 days → 5 minutes (99% faster)
- Confidence: exactly-once guarantee = no double-charges

---

## Q&A

**Recall 1:** What's the difference between at-least-once and exactly-once?

*Must-say:*
- At-least-once: retries until success, might duplicate
- Exactly-once: idempotency key deduplicates, safe for payments

**Probe 1:** Idempotency key is abc123. Server charges $100. Response lost. Client retries. What happens?

*Expected:*
- Server checks idempotency_key=abc123 in storage
- Finds previous result (already charged)
- Returns cached result (don't charge again)
- Client sees success

**Numeric 1:** 1000 payments/sec. 1% timeout + retry. How many idempotency checks vs charges?

*Working:*
- Charges: 1000/sec
- Timeouts: 10/sec (1%)
- Retries: ~10/sec (assume no cascading retries)
- Idempotency checks: 1000 + 10 = 1010/sec
- Charge operations: 1000/sec (retries don't create new charges)

---

## Questions for the Interviewer

- How do you generate idempotency keys? (UUID, hash of payload?)
- How long do you keep idempotency keys? (24 hours, forever?)
- What happens if idempotency storage goes down? (fallback to at-least-once?)
- Have you had duplicate-charge bugs despite exactly-once? (what went wrong?)
