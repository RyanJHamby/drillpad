# Multi-Region Disaster Recovery: RPO, RTO, and Data Consistency

## The Scenario

Your service is in us-east-1 (Virginia). A power outage blacks out the entire region.

All your servers go down. Customers can't access anything.

**Questions:**
1. How much data do you lose?
2. How long until customers are back online?
3. How do you keep data consistent across regions?

This lesson answers those three questions.

## Key Metrics: RTO and RPO

**RTO (Recovery Time Objective):** How long can your service be down?
- Example: "We need 15 minutes to failover to backup region"
- Business impact: How much revenue loss, customer churn?

**RPO (Recovery Point Objective):** How much data can you lose?
- Example: "We can lose 5 minutes of data"
- Business impact: Do customers notice missing transactions?

```
Timeline:
T0: Disaster strikes (power cut)
    Service down, data lost after last backup

T0+5min: Last backed-up data
    RPO window ends here (you can recover to this point)

T0+15min: Service recovered in backup region
    RTO window ends here (service back online)

T0+15min to T0+30min: Catch-up from backup
    Restored data up to T0+5min (oldest possible)
    
T0+30min: All systems recovered
    Running on secondary region, primary region still down
```

## RTO Levels

### Tier 1: Instant Failover (< 1 second)

**Setup:** Active-active replication (both regions serving traffic).

```
Primary (us-east-1):
  Handles 50% of traffic
  Replicates writes to backup (us-west-2) in < 10ms

Secondary (us-west-2):
  Handles 50% of traffic (same as primary)
  Receives replicated writes
  If primary fails, already has latest data
```

**Failover:** DNS TTL changes from primary to backup.
- [VERIFY] Modern DNS TTL: ~5-60 seconds
- Actually: clients keep old DNS for 5 seconds (TTL)
- [VERIFY] Load balancer detects primary down: ~1-5 seconds
- Total: ~5-10 seconds (not instant, but close)

**Cost:** Double infra (2x compute, 2x storage), replication overhead.

**Example:** Netflix, Stripe (money can't wait for slow failover)

### Tier 2: Fast Failover (1-5 minutes)

**Setup:** Warm standby (secondary region has servers, not handling traffic).

```
Primary (us-east-1):
  Handles 100% of traffic
  Replicates writes to backup in < 10ms

Secondary (us-west-2):
  Idle servers running "heartbeat" processes
  Not handling customer traffic
  If primary fails, spins up and takes over traffic
```

**Failover:** 
- Detect primary down: ~1 minute
- Spin up secondary region (scale up): ~2-3 minutes
- Point traffic to secondary: ~1 minute
- Total: ~3-5 minutes

**Cost:** 1.5x infra (full secondary, but not handling load).

**Example:** Most SaaS (AWS, Datadog, Slack tolerance: ~5 min down time)

### Tier 3: Manual Failover (> 5 minutes)

**Setup:** Cold standby (backup region has data, but no live servers).

```
Primary (us-east-1):
  Handles 100% of traffic
  Replicates writes to backup storage (S3, GCS)

Secondary (us-west-2):
  No running servers
  Latest data in snapshots (S3)
  On disaster: spin up servers from AMI, restore data, boot up
```

**Failover:**
- Detect primary down: ~5 minutes
- Spin up secondary servers from images: ~5-10 minutes
- Restore database from snapshots: ~10-30 minutes
- Run data integrity checks: ~5-10 minutes
- Point traffic to secondary: ~5 minutes
- Total: ~30-60 minutes (often manual)

**Cost:** 1.1x infra (backup storage, but no compute).

**Example:** Internal tools, databases with cheap data, non-critical services

## RPO Levels

### Tier 1: RPO = 0 (Synchronous Replication)

**Setup:** Every write is sent to both regions and waits for both to ACK.

```
Client:         Primary:        Secondary:
  write V1 ------>
                  write V1 ------>
                                 ✓ ACK
                  <--------- ✓ ACK
  <---------- ✓ ACK

Both regions have V1 before client is notified
RPO = 0 (no data loss)
```

**Cost:** Latency penalty.
- Round-trip to primary: ~5ms (us-east-1 to client in NYC)
- Additional round-trip to secondary: +20ms (us-west-2)
- Total write latency: ~25ms (was 5ms)

**Impact:** Write latency increases 5x.

**When to use:** Financial transactions (banking, stock trades).

### Tier 2: RPO = 1 minute (Asynchronous Replication with Batching)

**Setup:** Primary accepts write, replicates to secondary async (batch every 10 seconds).

```
T0:00: Client writes V1 to primary (us-east-1)
       Primary ACKs immediately (< 10ms)
       V1 is in primary's log
       
T0:10: Batch replication kicks off
       Sends V1, V2, V3, V4, V5 (all writes from last 10 sec)
       to secondary
       
T0:20: Secondary ACKs batch
       Now secondary has V1-V5

If primary dies at T0:15:
  V1-V5 are replicated (safe)
  V6 was added at T0:12 but not yet replicated
  V6 is lost (RPO = 10-20 seconds)
```

**RPO calculation:**
- Replication batches every 10 seconds
- Primary can crash between batches
- Max data loss: [VERIFY] 10-20 seconds

**Cost:** Minimal latency (primary responds immediately).

**When to use:** Analytics, logs, non-critical user data.

### Tier 3: RPO = 1 hour (Nightly Backups)

**Setup:** Daily snapshots replicated to secondary.

```
T0: Primary running normally
    Data: V1, V2, ..., V100

T0+24hours: Midnight snapshot
    Backup all data to S3 (primary region)
    Async copy to S3 (secondary region)
    
If primary dies at T0+12hours:
  Latest backup is 12 hours old
  All writes since T0 are lost
  RPO = 12 hours (worst case)
  Average RPO = 6 hours (if failures uniform)
```

**Cost:** Virtually free (snapshots, asynchronous backup).

**When to use:** Non-critical internal databases.

## The Consistency Problem

Replication introduces a new question: **what if data conflicts?**

### Scenario: Write to Primary, but Secondary is Stale

```
T0: Client writes V1 to primary (us-east-1)
    Primary ACKs
    
T1: Primary crashes
    Replication to secondary never completed
    Secondary doesn't have V1
    
T2: Secondary promoted to primary
    Secondary doesn't know about V1
    Other clients read old data
    
Result: Data loss and inconsistency
```

**Solution 1: RPO = 0 (Synchronous)**
- Wait for both regions to ACK before returning to client
- No data loss
- Downside: high latency (20-30ms per write)

**Solution 2: RPO = minutes (Async with Durability)**
- Primary writes to local disk immediately (durable)
- Async replicate to secondary
- If primary dies, restore from disk (if recoverable) or re-replicate from WAL log
- [VERIFY] Data loss window: 1-5 minutes (depends on replication frequency)

**Solution 3: RPO = hours (Snapshots with WAL)**
- Snapshot every hour
- Keep write-ahead logs (WAL) up to 24 hours
- On disaster: restore latest snapshot + replay WAL up to disaster
- Data loss: [VERIFY] max 1-5 minutes (latest committed data in WAL)

## Choosing Your RTO/RPO Strategy

```
Service         RTO     RPO           Strategy
--------        -----   -----         -----------
Banking         < 5m    0             Sync replication, active-active
                                      data centers

E-commerce      < 15m   1 min         Warm standby, async with batching
                                      
SaaS (Stripe)   < 5m    1 sec         Active-active, but separate DBs

Logging         < 1h    1 hour        Cold standby, nightly backups

Internal tools  < 2h    1-2 days      Simple replication, manual failover
```

## Diagrams

### RTO Timeline for Different Strategies

```
Disaster strikes at T=0

Active-Active (RTO ~10s):
  T=0:00:00 --X-- Primary down
  T=0:00:05 |  Detect failure (health check)
  T=0:00:10 |  Failover (DNS update)
  T=0:00:10 ✓ Service back online (secondary takes over)
  RTO = 10 seconds

Warm Standby (RTO ~3-5m):
  T=0:00:00 --X-- Primary down
  T=0:01:00 |  Detect failure
  T=0:02:30 |  Spin up servers in secondary
  T=0:03:30 |  Point traffic to secondary
  T=0:03:30 ✓ Service back online
  RTO = 3-4 minutes

Cold Standby (RTO ~30-60m):
  T=0:00:00 --X-- Primary down
  T=0:05:00 |  Detect failure (manual)
  T=0:10:00 |  Spin up secondary servers
  T=0:20:00 |  Restore database from snapshot
  T=0:30:00 |  Run integrity checks
  T=0:35:00 |  Update DNS, point to secondary
  T=0:35:00 ✓ Service back online
  RTO = 30-35 minutes
```

### RPO vs Write Latency Trade-off

```
RPO = 0 (Sync to both regions):
  ──────────────────────────────────
  Primary (us-east-1):  5ms
  Secondary (us-west-2):  +20ms (round-trip coast-to-coast)
  Total write latency:  25ms (5x slowdown)
  Data loss on primary failure: NONE

RPO = 10 sec (Async batch):
  ──────────────────────────────────
  Primary (us-east-1):  5ms
  Async batch to secondary: 0ms (not on critical path)
  Total write latency:  5ms (no slowdown)
  Data loss on primary failure: 0-10 seconds

RPO = 1 day (Nightly backup):
  ──────────────────────────────────
  Primary:  5ms
  Async snapshot: 0ms (background)
  Total write latency:  5ms (no slowdown)
  Data loss on primary failure: 0-24 hours

Tradeoff:
  RPO=0 → low data loss, high latency
  RPO=1day → high data loss, low latency
```

## Interview Section

### Q1: Your database is in us-east-1. You want RTO < 5 minutes and RPO < 1 minute. What's your strategy?

**Weak answer:** "Use backups."

**Strong answer:**
"Requirements: RTO < 5m, RPO < 1m

Backups alone won't work:
  - Nightly backup: RPO = 12-24 hours (fails requirement)
  - Even hourly backups: RPO = 1 hour (fails)

What we need:
1. Continuous replication (RPO < 1m)
   → Setup async replication to secondary region
   → Replicate every 10-30 seconds
   → RPO = 10-30 seconds ✓

2. Warm standby in secondary (RTO < 5m)
   → Pre-spin servers in secondary (idle)
   → On disaster: activate load balancer to secondary
   → RTO = 2-4 minutes ✓

Implementation:
  - Primary in us-east-1 (Virginia)
  - Secondary in us-west-2 (Oregon) with same infrastructure
  - Replication every 10 seconds (async)
  - Health checks to detect failure in < 1 minute
  - DNS failover (TTL 60s) or load balancer switch (< 1s)
  
Cost: ~1.5x infra (secondary region, not handling load)
Latency: No increase (async, not on critical path)"

### Q2: What's the difference between RPO and durability?

**Weak answer:** "They're the same."

**Strong answer:**
"Similar but different:

Durability: Does the data survive a single-machine crash?
  Answer: Yes, if written to disk (fsync)
  Cost: 1-5ms per write (disk latency)

RPO: How much data survives a regional disaster?
  Answer: Only data that was replicated to secondary
  Cost: network latency (replication round trip)
  
Example:
  Write V1 to disk (primary, us-east-1): durable, RPO=0 for primary
  Write V1 is NOT replicated to secondary yet
  Primary AND secondary both fail (meteor hit Virginia)
  V1 is lost (RPO failure, even though durable locally)

Solution:
  Synchronous replication: V1 is durable at both regions (true RPO=0)
  Async replication: V1 is durable at primary, not yet at secondary (RPO=minutes)

Trade-off:
  Durability: single-machine failure (cheap)
  RPO: regional failure (expensive, needs replication)"

### Q3: You have active-active replication across two regions. Both regions receive the same write concurrently. What happens?

**Weak answer:** "Data gets duplicated."

**Strong answer:**
"Depends on how you handle concurrency:

Scenario:
  Client writes V1 to Primary (us-east-1)
  Same client (different connection) writes V1 to Secondary (us-west-2)
  
Option 1: Last-Write-Wins (LWW)
  Primary: [id=123, value=V1, ts=T1]
  Secondary: [id=123, value=V1, ts=T2]
  
  If T2 > T1: Secondary wins, V1 overwrites
  If T1 > T2: Primary wins, V2 rejected (conflicts)
  
  Result: Single value, no duplication, but one write is silently lost

Option 2: Conflict Detection (CRDTs or Version Vectors)
  Primary: [id=123, value=V1, version=[primary:1, secondary:0]]
  Secondary: [id=123, value=V1, version=[primary:0, secondary:1]]
  
  Merge: version=[primary:1, secondary:1]
  Merge rule: pick value based on merge logic (e.g., union for sets)
  
  Result: Both operations are visible, no data loss

Option 3: Leader-based (Leader takes write, replicates)
  Both writes go to primary leader
  Primary serializes them: [V1 from region A, V1 from region B]
  Replicates to secondary
  
  Result: Both writes visible, ordered, no conflicts

Choice:
  Financial data: Option 2 or 3 (detect or prevent conflicts)
  Counters: Option 1 (LWW okay if occasional loss okay)
  Sets: Option 2 (CRDT unions, no loss)"

### Q4: Describe a cold-standby failover for a database.

**Weak answer:** "Copy data to backup, restore on failure."

**Strong answer:**
"Setup (before disaster):
  1. Primary database in us-east-1 (Virginia)
     - Live queries, reads, writes
     - Write-ahead logs (WAL) to S3 (us-east-1)
  
  2. Daily snapshot
     - Every night at 2 AM, snapshot all tables
     - Copy snapshot to S3 in secondary region (us-west-2)
     - Cost: ~30 min backup window, [VERIFY] 5-10 GB/hour (depends on data size)
  
  3. Secondary region (cold standby)
     - No running instances
     - AMI (machine image) ready in us-west-2
     - S3 bucket has latest snapshot

Failover process (on disaster):
  T0:00 - Disaster detected (primary completely down)
          Manual intervention required (or auto-detection)
  
  T0:05 - Engineer acknowledges, starts failover
  
  T5:00 - Spin up compute in us-west-2
          Launch instances from pre-built AMI
          Instances boot, dependencies start
  
  T10:00 - Restore database from S3 snapshot
          [VERIFY] 100 GB database → 20-30 min restore
          Data is at time T_snapshot (last backup)
  
  T20:00 - Optional: Replay WAL logs from primary
          WAL logs stored in primary S3 (us-east-1)
          If network available, re-download and replay
          Updates database to T_recovered (seconds before primary died)
  
  T25:00 - Integrity checks
          Run consistency checks, verify data
          [VERIFY] Large databases: 5-10 min check
  
  T30:00 - Update DNS, point to secondary
          DNS TTL 60-300s
          Clients see new primary within 1 min
  
  T35:00 - Service restored
          Failover complete, service back online
          
RPO: Snapshot time to disaster time
  Worst case: 12-24 hours (if snapshot at 2 AM, disaster at 2 PM)
  Average: 12 hours
  
Cost: ~1.1x infra (backup storage, minimal compute)"

### Q5: Numeric Exercise: RTO vs Cost Trade-off

Scenario: SaaS service with 10 million customers
  - Downtime cost: $100K per minute
  - Infra cost: $100K per month per region

Options:

**Option A: Active-Active (RTO = 10s)**
  Cost: $200K/month (2 regions running)
  Annual: $2.4M
  Downtime incidents per year: 1
  Cost if downtime: 10 min × $100K = $1M
  Total expected cost: $2.4M + $1M = $3.4M

**Option B: Warm Standby (RTO = 3-5m)**
  Cost: $150K/month (primary + idle secondary)
  Annual: $1.8M
  Downtime incidents per year: 1
  Cost if downtime: 4 min × $100K = $400K
  Total expected cost: $1.8M + $400K = $2.2M

**Option C: Cold Standby (RTO = 30-60m)**
  Cost: $110K/month (primary + backup storage)
  Annual: $1.32M
  Downtime incidents per year: 1
  Cost if downtime: 45 min × $100K = $4.5M
  Total expected cost: $1.32M + $4.5M = $5.82M

**Recommendation:**
  If downtime > 1 incident/year: Cold standby is actually MOST expensive
  At 1 incident/year, Warm standby is best (saves $1.2M vs cold, $1.2M vs active)
  
  But risk: if downtime increases to 2/year → warm standby still wins
  Active-active only wins if downtime > 2 incidents/year (not realistic)"

## When to Use / When NOT

| Scenario | RTO Need | RPO Need | Strategy |
|----------|----------|----------|----------|
| Banking | < 1m | 0 | Active-active, sync |
| E-commerce | < 15m | < 1m | Warm standby, async batch |
| SaaS | < 5m | < 5m | Warm standby, async |
| Internal tools | < 2h | < 24h | Cold standby, nightly |
| Non-critical logs | < 1d | < 7d | S3 archive, no failover |

## Checklist: Multi-Region DR Correctness

- [ ] Is RTO requirement realistic (not < 1m for cold standby)?
- [ ] Is RPO achievable (sync replication for RPO=0 cost acceptable)?
- [ ] Can secondary catch up on failover without data loss?
- [ ] Are WAL logs replicated for recovery?
- [ ] Is failover process automated or requires manual intervention?
- [ ] Are cross-region latency assumptions documented?
- [ ] Can you detect primary failure within RTO budget?
- [ ] Is DNS TTL appropriate for failover speed?
- [ ] Are there hidden dependencies (e.g., secondary needs SQS in primary)?

## Common Wrong Answers

1. "RPO=0 requires synchronous replication." → Actually yes, correct.
2. "Backups alone can achieve RTO < 5m." → NO, need replication + warm standby.
3. "Cold standby has zero cost." → NO, storage + testing + manual overhead.
4. "Active-active is always better." → NO, 2x cost, use only if RTO < 1m mandatory.
5. "RPO and RTO are the same." → NO, different metrics (data loss vs downtime).
6. "You can replicate to secondary without latency cost." → Only if async (not RPO=0).
7. "Failover happens automatically." → Depends on strategy (active-active yes, cold no).
