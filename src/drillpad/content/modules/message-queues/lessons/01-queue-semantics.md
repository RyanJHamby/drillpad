# Message Queues: Semantics and Guarantees

## Queue Guarantees

**At-least-once:** Message delivered ≥ 1 time (may duplicate)
**Exactly-once:** Message delivered = 1 time (no dupes, no loss)
**At-most-once:** Message delivered ≤ 1 time (may lose)

```
Payment system: "Charge $100"

At-least-once:
  Charged once, but retry duplicates → charged twice!
  
Exactly-once:
  Charged once, deduplication prevents double-charge
  
At-most-once:
  Maybe not charged (lost message)
```

## How to Achieve Exactly-Once

**Idempotency keys:** Client sends unique key with message

```
Payment:
  "Charge $100" + idempotency_key=xyz

Queue processes, stores result
If retry arrives (same key):
  Return cached result (don't recharge)
```

**Ordering:** Kafka partitions, SQS FIFO

```
Partition/FIFO: messages processed in order within partition

Message 1: "Deduct $100 from account"
Message 2: "Add $100 to account"

If out of order: might overdraft
In order: safe
```

## Real Example: Payment Pipeline

```
Client → API → Payment Queue → Payment Processor → DB

At-least-once (naive):
  API sends: {charge $100, user_id=123}
  Queue delivers to processor
  Processor crashes mid-charge
  API retries (same message)
  Processor charges again → $200!

Exactly-once (fix):
  API sends: {charge $100, user_id=123, idempotency_key=abc}
  Processor: check if abc already processed
  If yes: return cached response
  If no: process + store result under abc
  Retry: finds abc → returns cached response
  Result: charged once
```

## Performance Cost

Exactly-once requires:
- Store idempotency keys (cache, DB)
- Check before processing
- Handle failures atomically

Cost: ~1-10ms per message (slower than at-least-once)

Trade-off: correctness > speed for payments.
