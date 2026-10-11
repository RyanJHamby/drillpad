# Kafka Fundamentals - Topics, Partitions, Consumer Groups

## Why Streams Matter

Training data pipelines: Ingest → Transform → Store
```
Real-time events: 100K events/sec from user interactions
Need to: Process them in order, track progress, replay if needed

Queue (RabbitMQ): "Process once, forget"
Stream (Kafka): "Remember forever, multiple consumers, replay"
```

## Core Concepts

### Topic: The Event Stream
```
Topic: "user_interactions"
  Partition 0: [click_0, click_1, click_2, ...]
  Partition 1: [click_3, click_4, click_5, ...]
  Partition 2: [click_6, click_7, click_8, ...]

Each partition:
  - Immutable log (append-only)
  - Ordered (click_0 before click_1)
  - Persistent (stored on disk, survives restart)

Consumers track position: "I've processed up to offset 1000"
```

### Partitioning: Why It Matters

```
Topic has 3 partitions (parallelism)
Consumer 1: Reads partition 0
Consumer 2: Reads partition 1
Consumer 3: Reads partition 2

Each consumer processes independently
Total throughput: 3x single consumer

Key question: Which partition gets each event?
  By default: Round-robin (partition 0, 1, 2, 0, 1, 2, ...)
  Better: By user_id (all events for user_1 → partition 0)
          Ensures ordering per user
```

### Consumer Groups: Multiple Readers

```
Topic: "user_interactions" (3 partitions)

Consumer Group A (data pipeline):
  Consumer A1: Reads partition 0
  Consumer A2: Reads partition 1
  Consumer A3: Reads partition 2

Consumer Group B (training):
  Consumer B1: Reads partition 0
  Consumer B2: Reads partition 1
  Consumer B3: Reads partition 2

Same events, two independent consumer groups
Both can replay from beginning (offsets independent)
```

## Real-World: ML Training Pipeline

```
Topic: "training_events" (raw user interactions)
  - Click, hover, purchase, search
  - 10M events/day
  - 3 partitions (10 producers pushing data)

Consumer Group: "training_pipeline"
  - Process events in micro-batches (every 5 seconds)
  - Enrich: add user features (age, location)
  - Store: write to data warehouse (Parquet)
  - Checkpoint: save offset every batch

If crash:
  - Resume from last checkpoint
  - No duplicate processing (exactly-once)
  - No data loss
```

## Offset Management: The Key Insight

```
Offset: Position in partition log

Consumer reads:
  Offset 0: event_0
  Offset 1: event_1
  Offset 2: event_2
  ...
  Offset 1000: event_1000

Consumer crashes at offset 500
  Restart: resume from offset 500
  Not offset 0 (don't reprocess 0-499)
  Not offset 600 (don't skip 500-599)

Exactly once: Commit offset only after processing succeeds
```

## Interview Pattern: Partition Strategy

```
Q: "You have 1M events/sec of user clicks. Kafka topic with 10 partitions.
   How do you partition?"

Weak answer:
  "Round-robin, balance load"
  (❌ Loses ordering per user)

Strong answer:
  "Partition by user_id:
  
  1. Why: User clicks must be in order
     - User clicks button → sees result
     - Process out of order → wrong feature values
  
  2. How:
     producer.send(
       topic='clicks',
       value=click_event,
       key=user_id  ← hash this to choose partition
     )
  
  3. Result:
     - user_1 events → partition 0
     - user_2 events → partition 1
     - user_3 events → partition 0
     - All per-user events ordered
  
  4. Scaling:
     10 partitions: 1M events/sec ÷ 10 = 100K/sec per partition (OK)
     Need more throughput? Add partitions
  
  5. Consumer group:
     10 consumers (one per partition)
     Each processes their partition independently
     Can crash and resume without reprocessing
  
  6. Trade-off:
     Ordering per user, but not global ordering
     OK: clicks from user_1 and user_2 can be interleaved
     Not OK: user_1's clicks out of order"

Why this signals good judgment:
  - You understood ordering requirement (key by user)
  - You knew how to partition (key-based routing)
  - You understood scaling (more partitions = more throughput)
  - You had consumer strategy (one per partition)
```

## Checklist: Kafka in Production

- [ ] Topic has enough partitions (throughput > lag)
- [ ] Partition key strategy (ordered by what?)
- [ ] Consumer group offset management (committed, not lost)
- [ ] Replication factor = 3 (survives node failure)
- [ ] Monitoring: consumer lag (how far behind real-time?)
- [ ] Retention policy (keep forever or 7 days?)
- [ ] Exactly-once semantics (idempotent processing)

## What This Signals

- You've built data pipelines at scale
- You understand ordering and partitioning
- You can troubleshoot consumer lag
- You know exactly-once matters for training data
