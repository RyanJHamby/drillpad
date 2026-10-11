# Strong Consistency: Definition, Cost, When You Need It

## Definition: What Does "Strong" Mean?

```
Strong Consistency = Linearizability

Write(100) → ACK → all subsequent reads return 100+

Not just "all replicas agree" (eventual)
But "all reads after write see the write"

Trade-off: Consistency for latency
```

## Cost of Strong Consistency

```
Payment system:
  Write(charge $100) → propagate to all 3 replicas → ACK to client
  
  Latency = slowest replica + consensus overhead
  = 10ms (local) + 150ms (cross-region) + 5ms (fsync) = 165ms
  
Eventual consistency:
  Write(charge $100) → ACK immediately → async replicate
  
  Latency = fsync only = 5ms
  
Cost: 165ms vs 5ms = 33x latency for consistency
```

## When You MUST Have Strong Consistency

```
❌ Inventory system
  "Only 1 item left"
  Strong consistency would serialize writes
  Eventual consistency acceptable (worst: oversell 1-2 items)

✅ Payment system
  "Charge $100"
  MUST be strongly consistent
  Double-charging is catastrophic
  
✅ Brokerage account
  "Transfer $1M"
  MUST be consistent
  Money can't be in two places

✅ Order matching
  "Match order immediately"
  MUST be consistent
  Can't have two matches for same order
```

## Interview Pattern

```
Q: "Design payment system. Consistency requirement?"

Answer:
  "Strong consistency required (can't double-charge).
  
  Trade-off: 165ms latency vs eventual (5ms).
  
  Solution:
  1. Accept latency for payments (165ms is acceptable)
  2. Use quorum writes (majority replica gets write)
  3. Reconciliation job (catch edge cases)
  
  Why not eventual:
  - 0.1% failure rate (1 in 1000 charges) = $10k/day loss
  - Cost of strong consistency (165ms) << cost of failures"
```

## CAP Theorem Applied

```
Payment system during network partition:
  - Consistency: must prevent double-charge
  - Availability: can be down briefly
  
  Choose: Consistency (CP)
  → Partition happens: stop accepting writes until healed
  
Notification system during partition:
  - Consistency: approximate is fine
  - Availability: must deliver notifications
  
  Choose: Availability (AP)
  → Partition happens: deliver with best-effort (might be stale)
```

