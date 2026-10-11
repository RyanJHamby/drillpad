# Message Queues: Kafka Partitions & Consumer Groups

## Why Kafka?

SQS/RabbitMQ delete messages after consumption. Kafka keeps messages on disk by default (retention policy), enabling:
- Re-processing: rewind consumer to old offsets
- Audit: replay entire stream
- Broadcasting: multiple consumers read same messages

```
SQS:
  Producer → Queue → Consumer → Message deleted
  Reprocessing? Can't (message gone)

Kafka:
  Producer → Partition 0 → Consumers
          → Partition 1
          → Partition 2
  
  Messages stay for N days (default 7)
  Consumer offset tracks "how far we've read"
  Can rewind and re-read
```

## Partitions: Why Sharding?

Single Kafka topic needs 1M messages/sec. Single partition can't keep up (disk I/O bound).

```
Solution: Partition the topic

Topic: "orders"
  Partition 0: messages for user_id % 3 == 0
  Partition 1: messages for user_id % 3 == 1
  Partition 2: messages for user_id % 3 == 2

Producer:
  Order for user 123 → hash(123) % 3 = 0 → Partition 0
  Order for user 456 → hash(456) % 3 = 0 → Partition 0
  Order for user 789 → hash(789) % 3 = 2 → Partition 2
  
Result: 3 parallel writers, 3x throughput
```

**Within-partition ordering:** Partition 0 processes orders in FIFO order. Partition 2 is independent.

**Cross-partition ordering:** No guarantee (Partition 0 user gets filled before Partition 2 user).

## Consumer Groups

One partition can have multiple consumers, but one consumer per partition to avoid duplicates.

```
Topic "orders", 3 partitions
Consumer Group "payment-processors"

Setup:
  Consumer 1: reads Partition 0
  Consumer 2: reads Partition 1
  Consumer 3: reads Partition 2
  
  Each partition has 1 consumer → no duplicates

Scale-out: add 4th consumer?
  Kafka rebalances:
    Partition 0 → Consumer 1
    Partition 1 → Consumer 2
    Partition 2 → Consumers 3 & 4 share
    
  Problem: same message processed twice (race condition)
  Solution: max 1 consumer per partition
            if 4 consumers + 3 partitions → 1 consumer idle
```

## Consumer Lag: Falling Behind

Consumer offset = "next message to process"
Producer offset = "latest message"

```
Partition 0:
  Offsets: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ...]
  Producer offset: 10 (latest)
  Consumer offset: 7 (processed up to #6)
  
  Lag = 10 - 7 = 3 messages behind
  
  If 1000 msg/sec and lag = 3:
    Consumer is ~3ms behind (real-time)
  
  If 1000 msg/sec and lag = 10,000:
    Consumer is ~10 seconds behind (backlog)
```

## Lag Monitoring: Production Critical

```
Alert thresholds:

1. Absolute lag > 100,000:
   Consumer falling far behind
   Action: add more consumers (rebalance)

2. Lag growth rate > 100 msg/sec:
   Consumer slower than producer
   Action: check CPU/disk, scale consumer

3. Lag never reaches 0:
   Consumer stuck (deadlock?)
   Action: restart consumer

Real example (payment processing):
  Lag = 50,000 messages
  Producer = 10,000 msg/sec
  → 5 seconds of unprocessed payments
  → customers see "payment pending" for 5s (bad UX)
```

## Retention Policy

```
By default: keep messages for 7 days
  Partition 0 has 7 days × 100k msg/sec × 1KB = ~600GB on disk
  After 7 days: oldest messages deleted

By size: keep latest 1TB
  Partition 0 ~1TB
  Oldest message deleted when new message added

By time: keep for 1 hour (real-time analytics)
  Messages deleted after 1 hour
  Consumer slow? Can't rewind past 1 hour

Risk: consumer lag > retention window
  Consumer lag = 8 days, retention = 7 days
  Oldest lag message already deleted
  → Consumer loses messages (unreplayable)
```

## Real Example: Payment Queue

```
Topic: "payment-requests"
Partitions: 4 (one per payment processor)
Retention: 30 days (compliance requirement)
Consumer Group: "payment-processors"

Scenario: Payment processor crashes
  Lag starts growing: 0 → 100 → 500 → 1000
  Alert fires at lag > 100
  
  Operator: restart processor + rebalance
  Processor comes back: lag starts decreasing
  
  Monitor: lag → 900 → 500 → 100 → 0
  After 2-3 min: caught up, back to real-time

Scenario: Code change broke processor
  New version redeployed
  Processor processes at 100 msg/sec (was 10k msg/sec)
  Lag grows: 0 → 500 → 2000 → 5000 (log scale)
  Alert + PagerDuty page
  
  Operator: rollback deployment
  Lag decreases as old version catches up
```

## Offset Management

Consumer must track: "I've processed up to offset 42, next is 43"

**Option 1: Kafka stores offset**
```
Consumer 1 reads messages 0-10
Consumer 1 commits offset 10
Kafka stores: consumer_group="payment" partition=0 offset=10

Consumer 1 crashes
Consumer 1 restarts
  Kafka says: start at offset 11 (resume from crash)
```

**Option 2: Application stores offset**
```
Consumer reads message 42
Application writes to DB: {consumer_group, partition, offset=42}
Consumer crashes
  On restart: query DB, find offset=42, resume

Advantage: exactly-once semantics (offset + message in same transaction)
Disadvantage: complexity, extra DB calls
```

## Interview Questions

**Q: "Your Kafka consumer is slow. How do you diagnose if it's a producer bottleneck or consumer issue?"**

A: "Check lag trend. If lag is constant (e.g., always lag=500), producer is fast, consumer is consistently slow. If lag grows monotonically (0→5000), consumer is falling behind. For producer-side: check replication factor + acks setting (acks=all = slow). For consumer: check batch size, linger time, CPU usage via jconsole. Profile the consumer code for blocking calls (DB queries, external API)."

**Q: "Design a payment processing pipeline with Kafka. How many partitions? Consumer groups?"**

A: "Partitions by payment_id % N for ordering within user. If 100k payment/sec, need ~10-20 partitions (assuming 5k-10k/sec per partition). Consumer group 'payment-processors' with one consumer per partition. Separate consumer groups for: audit logging, fraud detection, reporting. Retention: 30 days (compliance). Lag alert if > 1000 (humans waiting), growth rate > 100 msg/sec. Deploy consumer with graceful shutdown: stop accepting new messages, finish in-flight, commit offset."

**Q: "Consumer lag is 100k but you only have 7 days retention. What happened?"**

A: "Consumer was down for 8+ days (offset 8 days old, but retention is 7 days). Old offset was garbage collected. Can't resume from old position. Options: (1) replay from beginning (but would reprocess recent messages twice — need idempotency keys); (2) skip to latest offset (lose 8 days of data); (3) restore from backup or data lake if available. Lesson: set retention policy >= max tolerable downtime, or implement offset storage in database with backup restoration procedure."
