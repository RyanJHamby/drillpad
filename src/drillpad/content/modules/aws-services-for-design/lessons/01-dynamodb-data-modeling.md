# DynamoDB Data Modeling

## Keys & Partitioning

```
Primary key: (PK, SK) determines partition and sort

PK (partition key):
  ├─ Hash-based sharding: hash(PK) % N partitions
  ├─ All items with same PK live in same partition
  └─ Must be queryable (user_id, org_id, etc.)

SK (sort key):
  ├─ Sorts items within partition
  ├─ Range queries: SK BETWEEN start AND end
  └─ Examples: timestamp, version, attribute

Bad PK (hot partition):
  ├─ PK = "company" (only 1 company!)
  ├─ All items hash to same partition
  ├─ Partition gets throttled
  └─ Max: 40K WCU per partition

Good PK (even distribution):
  ├─ PK = user_id (millions unique)
  ├─ Distribution even, no hot keys
  └─ Scales to 40K WCU per user (unlikely to hit)
```

## Single-Table Design

```
Naive (multi-table):
  ├─ users table
  ├─ orders table
  ├─ payments table
  └─ Query patterns: 5 tables, 5 queries
  
Problem: complex joins, app-side logic

Single-table design:
  
  PK: entity_id (user_123, order_456, payment_789)
  SK: entity_type#timestamp (user#2025, order#2025-01-01, payment#2025-01-01T10:30)
  
  Query: all user data
    └─ Query(PK=user_123) → all user records
  
  Query: all orders by user
    └─ Query(PK=user_123, SK BEGINS_WITH "order#")
  
  Benefit:
    ├─ One table, one partition
    ├─ No joins (application-level denormalization)
    ├─ Fast queries (single partition read)
```

## GSI (Global Secondary Index)

```
Main table:
  PK: user_id
  SK: timestamp
  Query: "all events for user_123" (fast)

Problem: "find all events in timestamp range (across all users)"
  ├─ Scan entire table (slow, expensive)
  └─ Solution: GSI

GSI:
  PK: timestamp (GSI partition key)
  SK: user_id (GSI sort key)
  
  Query: timestamp BETWEEN 2025-01-01 AND 2025-01-31
    └─ Fast (GSI indexed)
  
  Cost:
    ├─ Storage: duplicate data (main table + GSI)
    ├─ Write: every item write updates main + GSI
    ├─ Extra WCU: ~2x (main + GSI)
    └─ Trade-off: query speed vs write cost
```

## Throttling & Capacity

```
Throughput modes:

On-demand:
  ├─ Pay per request (no capacity planning)
  ├─ Cost: high ($1.25 per 1M read units)
  └─ Use: unpredictable traffic

Provisioned:
  ├─ Fixed capacity: 100 WCU, 100 RCU
  ├─ Cost: low ($0.47 per WCU/month, $0.09 per RCU/month)
  └─ Use: predictable traffic
  
Throttling:
  ├─ Exceed provisioned capacity → 400 error
  ├─ Mitigation: exponential backoff
  └─ Prevention: scale capacity ahead of demand
```

## Consistency

```
Strong consistency:
  ├─ Read from primary partition (always latest)
  ├─ Latency: +5-10ms (leader replica)
  └─ Cost: same WCU

Eventual consistency (default):
  ├─ Read from any replica (may be stale)
  ├─ Latency: lower
  └─ Replication: ~1ms lag
```

---

## Interview Checklist

- [ ] PK must distribute evenly (no hot partitions)
- [ ] SK enables range queries
- [ ] Single-table design: denormalize to reduce joins
- [ ] GSI: duplicate index for alternate query patterns
- [ ] Throttling: understand WCU/RCU costs
- [ ] Consistency: eventual ok for most, strong for critical

## Common Wrong Answers

- ❌ "Use company_id as PK" — hot partition if few companies
- ❌ "Multi-table design" — joins inefficient in DynamoDB
- ❌ "No GSI" — can't support alternate query patterns
- ❌ "Ignore WCU" — throttling kills production performance
