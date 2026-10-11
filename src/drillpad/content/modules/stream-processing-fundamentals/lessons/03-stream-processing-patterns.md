# Stream Processing Patterns - Exactly-Once, Backpressure, Scaling

## Exactly-Once Semantics

Problem: Consumer crashes while processing event
```
Event 1: Write feature → crashes
Event 2: Restart → reprocess Event 1 (duplicate!)
Result: Feature count is wrong (counted twice)
```

Solution: Idempotent processing + offset commit
```
Process event:
  1. Update feature store (idempotent, use insert-or-update)
  2. Commit offset (to Kafka, saying "I processed up to here")

If crash:
  Restart → resume from committed offset
  Event 1: Already in feature store (idempotent update, no error)
  Continue from Event 2

Result: No duplicates, no loss
```

## Backpressure: Pushing Back

```
Consumer processing rate: 1000 events/sec
Producer rate: 10000 events/sec

Queue fills up:
  Queue size: 1000 → 2000 → 5000 → 10000 → memory exhausted

Solution: Backpressure
  Queue full? Tell producer: "Stop sending, I'm overloaded"
  Producer waits
  Consumer catches up
  Producer resumes

Kafka-level backpressure:
  Consumer lag = producer_offset - consumer_offset
  If lag > threshold (e.g., 100K), slow down consumption
```

## Scaling Stateful Pipelines

Problem: One consumer can't keep up
```
Topic: 10 partitions, 100K events/sec per partition
One consumer: Can only process 500K events/sec total
Lag: Growing (consumer falling behind)

Solution: Scale to multiple consumers
  Partition 0 → Consumer 1
  Partition 1 → Consumer 2
  ...
  Partition 9 → Consumer 10

Now: 10 consumers, each handles 100K events/sec
Total: 1M events/sec (10x scaling)
```

Challenge: Stateful scaling
```
Consumer 1 was handling partitions 0-2 (had state for users 1-100)
Now: Partition 0 → Consumer 1, Partition 1 → Consumer 2, Partition 2 → Consumer 3

State for users 30-50 moves from Consumer 1 to Consumer 2
Where does the state live?

Option A: In-memory (lose it when rebalance) → Bad
Option B: External store (Redis, RocksDB) → Slower but safe
Option C: Stateless operators (no per-user state) → Scales better
```

## Interview Pattern: Stream Processing at Scale

```
Q: "You need to process 1M events/sec for training.
   Events need per-user aggregation (click count per minute).
   How do you scale and ensure exactly-once?"

Weak answer:
  "Use many consumers, store state in memory"
  (❌ Lose state on restart, not exactly-once)

Strong answer:
  "Exactly-once + scaling architecture:
  
  1. Topic design:
     10 partitions (1M events/sec ÷ 100K per partition)
     Partition key = user_id (all user events → same partition)
  
  2. Consumer group:
     10 consumers (one per partition)
     Each consumer handles 100K events/sec
  
  3. State management:
     Per-user click counts: stored in RocksDB (local disk)
     Not in-memory (survives restart)
     
     RocksDB persists:
       user_1 → 23 clicks this minute
       user_2 → 15 clicks this minute
  
  4. Exactly-once flow:
     Process event:
       1. Read state (user_id → click_count)
       2. Increment: click_count + 1
       3. Write back to RocksDB
       4. Commit offset to Kafka
     
     If crash between step 3 and 4:
       State is written, but offset not committed
       Restart: reprocess same event
       RocksDB: idempotent (increment again) → overwrite
       Result: No duplicate effect
  
  5. Scaling concern: Rebalancing
     Consumer 2 dies
     Its 100K events/sec go to Consumer 1 (overload)
     Rebalance: Assign partition to Consumer 1 (has state in RocksDB)
     
     But state is on Consumer 2's disk!
     Solution: RocksDB checkpoint to network store (HDFS, S3)
       Every minute: flush state
       On rebalance: restore from checkpoint
  
  6. Monitoring:
     - Consumer lag (if > 100K, scale up)
     - RocksDB size (per partition, monitor growth)
     - Checkpoint success rate (crucial for recovery)
     - Processing latency (should be <1s per event)
  
  7. Performance:
     10 consumers * 100K events/sec = 1M/sec total
     RocksDB write latency: ~1ms per update
     Kafka commit latency: ~10ms (batched)
     Per-event latency: ~20ms (acceptable for training)
  
  Cost:
     10 Kafka brokers (replication = 3)
     10 consumer instances (8 vCPU, 32GB each for RocksDB)
     Network storage for checkpoints (HDFS or S3)
     Total: ~$50K/month at scale"

Why this signals good judgment:
  - You understood per-user state (partition by user)
  - You knew RocksDB for local state (survives restart)
  - You had checkpoint strategy (rebalance recovery)
  - You understood idempotence (exactly-once)
  - You could estimate performance and cost
```

## Checklist: Stream Processing in Production

- [ ] Exactly-once semantics (idempotent + offset commit)
- [ ] State management (external store, not in-memory)
- [ ] Late data handling (allowed lateness, retractions)
- [ ] Backpressure (consumer lag monitoring)
- [ ] Scaling strategy (how many consumers?)
- [ ] Rebalancing recovery (state checkpoints)
- [ ] Monitoring (lag, latency, throughput)

## What This Signals

- You've scaled streaming systems (multiple consumers, state management)
- You understand failure modes (exactly-once, rebalancing)
- You can estimate performance and cost
- You know the tradeoffs (latency, accuracy, infrastructure cost)
