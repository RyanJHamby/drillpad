# AWS Messaging & Streaming: SQS vs SNS vs EventBridge

## SQS (Simple Queue Service)

```
Use case: producer → queue → consumer(s)

Push model:
  ├─ Producer: SendMessage(queue_url, msg)
  ├─ Consumer: ReceiveMessage(queue_url)
  └─ Polling: consumer pulls, not push

Guarantees:
  ├─ At-least-once (message may be delivered 2x)
  ├─ FIFO queue: exactly-once, ordered
  ├─ Standard queue: best-effort order
  
  Cost:
    ├─ $0.40 per million requests
    ├─ Free tier: 1M requests/month
    └─ Cheap

Retention:
  ├─ Default: 4 days
  ├─ Max: 14 days
  ├─ Use: short-term buffering, not archival

Visibility timeout:
  ├─ Message received: invisible for 30s
  ├─ Consumer processes and deletes
  ├─ If crash: message re-appears, another consumer retries
  └─ Prevents duplicate processing (if idempotent)

Example:
  ├─ Producer: POST /order → sends to SQS
  ├─ SQS: buffers orders
  ├─ Consumer: polls SQS, processes order, deletes
```

## SNS (Simple Notification Service)

```
Use case: producer → many consumers (fan-out)

Push model:
  ├─ Producer: Publish(topic, msg)
  ├─ SNS: broadcasts to all subscribers
  └─ Subscribers: SQS, Lambda, email, HTTP endpoint

Fan-out architecture:
  ├─ Order placed → SNS topic
  ├─ Subscribers:
  │  ├─ SQS (payment service)
  │  ├─ SQS (inventory service)
  │  └─ Lambda (send confirmation email)
  └─ All get same message simultaneously

Delivery semantics:
  ├─ Best-effort delivery (may lose if subscriber down)
  ├─ No ordering guarantee
  └─ Retry: SNS retries for exponential backoff

Cost:
  ├─ $0.50 per million publishes
  ├─ $0.50 per million deliveries to SQS
  └─ Higher than SQS alone (but enables fan-out)
```

## EventBridge

```
Use case: event routing (SNS on steroids)

Features:
  ├─ Rules: filter events by pattern matching
  ├─ Targets: SQS, Lambda, SNS, Kinesis, etc.
  ├─ Retry: configurable exponential backoff
  └─ DLQ: dead-letter queue for failed events

Example:
  ├─ Event: EC2 instance state change
  ├─ Rule: if state == "running" AND region == "us-east-1"
  ├─ Target: send to SQS for auto-scaling logic
  └─ Result: conditional routing

Cost:
  ├─ $0.35 per million events published
  └─ Cheaper than SNS per message, but more features
```

## Comparison

```
SQS vs SNS vs EventBridge:

                SQS         SNS           EventBridge
Pull/Push       Pull        Push          Push
Fan-out         No          Yes           Yes (rules)
Order           FIFO opt    No            No
Filtering       No          No            Yes (patterns)
Retry           Yes         Yes           Yes
Cost/million    $0.40       $1.00         $0.35
Use case        Queue       Broadcast     Event routing

Choose:
  ├─ SQS: simple queue, async processing
  ├─ SNS: broadcast same message to many
  └─ EventBridge: conditional routing, complex patterns
```

---

## Interview Checklist

- [ ] SQS: at-least-once, FIFO for ordering
- [ ] SNS: fan-out to multiple subscribers
- [ ] EventBridge: rule-based filtering and routing
- [ ] Visibility timeout: prevents duplicate processing
- [ ] Cost: SQS cheap, SNS higher, EventBridge middle
- [ ] Retention: SQS 4-14 days (not archival)

## Common Wrong Answers

- ❌ "SNS delivers to all subscribers" — if one is down, no retry
- ❌ "SQS orders messages" — only FIFO variant guarantees order
- ❌ "EventBridge is more expensive" — actually cheaper per message
