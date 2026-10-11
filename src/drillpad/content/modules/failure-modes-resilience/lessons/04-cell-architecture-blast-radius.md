# Cell Architecture: Blast Radius Containment and Independent Failure Domains

## Why This Interview Matters

At scale (Netflix, AWS, Meta), one region's failure shouldn't break the entire system. Cell-based architecture is how you contain failures: isolate domains, shard state, replicate control planes. This is critical for SRE, infrastructure, and systems roles.

**Core insight:** A cascading failure in one cell should not propagate to others. Blast radius is bounded by design, not hope.

---

## First Principle: Blast Radius and Isolation

When you deploy software globally, failures are inevitable:
- Datacenter power loss
- Network partition
- Buggy deployment to one region
- Storage system failing in one zone

**Without cells:** One failure cascades globally.
```
Global state (one database):
  All regions → single database
  Database fails → entire system down
  One region's bug → spreads everywhere
```

**With cells:** Failure is contained.
```
Cell-based (each region independent):
  Region 1: cell-1 (data, control plane, services)
  Region 2: cell-2 (separate data, control plane)
  Region 3: cell-3 (separate data, control plane)
  
  Cell-1 fails → Region 1 degraded
  Regions 2 & 3 unaffected
```

---

## Cell Architecture: The Core Pattern

A cell is a complete, independent replica of your system serving a geographic region or shard:

```
┌─────────────────────────────────────────────────────────────────┐
│ GLOBAL ORCHESTRATION LAYER (DNS, traffic policy, monitoring)    │
└──────────────┬──────────────────────────┬──────────────┬────────┘
               │                          │              │
        ┌──────▼──────┐          ┌────────▼────┐   ┌───▼───────┐
        │  CELL-1     │          │  CELL-2     │   │  CELL-3   │
        │ (US-EAST)   │          │ (US-WEST)   │   │ (EU)      │
        ├─────────────┤          ├─────────────┤   ├───────────┤
        │ API Tier    │          │ API Tier    │   │ API Tier  │
        │ Service Tier│          │ Service Tier│   │ Service   │
        │ Data Tier   │          │ Data Tier   │   │ Data Tier │
        │ Cache Tier  │          │ Cache Tier  │   │ Cache Tier│
        │ Control Plane│         │ Control Pl. │   │ Control   │
        └─────────────┘          └─────────────┘   └───────────┘
        
        Independent failure domain:
        - Failure in Cell-1 doesn't affect Cell-2, Cell-3
        - Traffic reroutes away from failed cell
        - Cell can be independently deployed, updated
```

**Key properties:**
1. **Data replication per cell:** Each cell has its own copy of critical data. Replication between cells is asynchronous (eventual consistency).
2. **Independent control plane:** Each cell has its own metadata store, orchestrator, config repository.
3. **Graceful degradation:** If a cell is unavailable, traffic shifts to other cells. Capacity per cell is designed to handle ~150% of normal load (to absorb traffic from one failed cell).
4. **Blast radius:** Failure affects only the shard/region served by that cell. Other cells continue.

---

## Example: Netflix Content Delivery Cell Architecture

**Setup:** Netflix has users globally. Each region (US, EU, APAC) is a cell.

```
Netflix Cell Example:
┌─────────────────┐
│ Edge DNS        │ ← Global entry point
├─────────────────┤
│ Is US-EAST up?  │ ← Health check each cell
│ Is US-WEST up?  │
│ Is EU up?       │
└────────┬────────┘

If US-EAST is down:
  - DNS routes new users to US-WEST, EU
  - Existing users on US-EAST see degradation (local retries, then failover)
  - EU and US-WEST unaffected
```

**Per-cell infrastructure:**
```
Cell: US-EAST-1
├─ API servers (load balanced)
├─ Content delivery (CDN caches)
├─ Metadata store (which user watched what)
├─ Recommendation engine (ML inference)
├─ Control plane (scheduler, deployment, config)
└─ Monitoring (metrics, logs, traces — local)

Each cell is a complete stack. No shared database across cells.
```

**Scenario: Metadata database in US-EAST fails**

Timeline:
```
T=0: Database in US-EAST crashes
     Queries start timing out (30s timeout)
     
T=1s: Circuit breaker opens
     API servers stop calling database (fail fast)
     Serve stale data from cache (2-hour TTL)
     
T=5s: Cache hits expire for recently updated content
     Requests start failing (no data available)
     Monitoring alert: "US-EAST metadata unavailable"
     
T=10s: SRE acknowledges alert
     US-EAST cell marked "unhealthy"
     
T=15s: DNS updated
     New traffic diverted to US-WEST, EU
     Existing US-EAST sessions get connection error
     Clients reconnect to US-WEST
     
T=20s: Most users have reconnected
     US-EAST still serving ~20% (stuck connections)
     
T=30min: Database recovered
     US-EAST cell re-enabled
     Traffic rebalances
```

**Cost analysis:**
- Without cells: All Netflix users affected (potential $10K/min revenue loss)
- With cells: ~10% of US-EAST users affected for ~15 minutes (~$1-2K loss)
  - Affected users reconnect to other cells
  - Other 90% + all EU + all APAC unaffected

---

## Architecture Patterns: How Cells Coordinate

### Pattern 1: Sharding by Geography

Each cell serves a specific region. Users stick to their region unless region is down.

```
User in San Francisco → routes to US-WEST cell
User in London → routes to EU cell
User travels to London → switches DNS to EU (eventual)
```

**Tradeoff:**
- Pro: Minimal cross-region latency, data sovereignty
- Con: Regional capacity imbalances (all US load on US cell during peak hours)

### Pattern 2: Sharding by Tenant/Customer

Each cell serves a specific customer or customer group (multi-tenant isolation).

```
Cell-1: Customer A (all their data, control plane)
Cell-2: Customer B (all their data, control plane)
Cell-3: Customer C (all their data, control plane)
```

**Tradeoff:**
- Pro: Total failure isolation (if Customer A's cell fails, Customers B & C unaffected)
- Con: Can't easily shift load (if Customer A's cell is overloaded, can't use Customer B's spare capacity)

### Pattern 3: Hybrid (Region + Shard)

```
Cell-1-A: US-EAST, Customer A
Cell-1-B: US-EAST, Customer B
Cell-2-A: US-WEST, Customer A
Cell-2-B: US-WEST, Customer B
```

**Tradeoff:**
- Pro: Regional + customer isolation
- Con: More operational complexity

---

## Cross-Cell Replication: How Cells Stay in Sync

Data is replicated asynchronously between cells (strong consistency would be too slow).

```
User writes in US-EAST-1:
  T=0:  Write lands in US-EAST-1 primary
  T=10ms: Write replicated to US-WEST-2
  T=50ms: Write replicated to EU-1
  
If user travels between regions:
  Might see stale data for a few seconds
  Eventually consistent (guaranteed)
```

**Implementation:**
```cpp
struct CellWrite {
  key: string,
  value: blob,
  timestamp: logical_clock,  // Lamport clock for ordering
  origin_cell: string,
  replication_status: {
    us_east: acked,
    us_west: pending,
    eu: pending,
  }
};

// Pseudo-code
void replicate_between_cells(write) {
  for (each remote cell) {
    async_send(write);  // Don't wait for ack
  }
}

// Remote cell receives
void apply_remote_write(write) {
  if (write.timestamp > local_clock) {
    apply(write);
    update_clock(write.timestamp);
  } else {
    // Older write, ignore (already applied)
  }
}
```

**Blast radius of replication lag:**
- If US-EAST is slow to replicate, users see stale data
- But US-EAST failures don't propagate (async = decoupled)

---

## Monitoring Within a Cell: Failure Detection

Each cell has independent monitoring. If a cell's monitoring goes down, the global orchestrator doesn't know it's down.

```
Cell-1 Monitoring:
  - Metrics collection (Prometheus-like)
  - Log aggregation (ELK-like)
  - Distributed tracing (Jaeger-like)
  - Local alerting

Global Orchestration:
  - Health checks to each cell
  - If health check fails 3 times, mark cell unhealthy
  - Divert traffic away
```

**Failure scenario: Cell-1 monitoring system crashes**

```
T=0: Monitoring in Cell-1 fails (database down)
     Local alerting is blind

T=1m: Global orchestrator sends health check
      Cell-1 APIs respond (they're fine, don't know about monitoring)
      Health check passes (false negative)
      
T=5m: Databases in Cell-1 have issues, no one notices
      User impact growing
      
T=10m: User complaints accumulate
       Global team investigating
       Finally detect Cell-1 is degraded
       Traffic diverted
```

**Fix:**
- Separate monitoring infrastructure per cell (don't over-centralize)
- Distributed health checks (quorum-based, not single point)
- Fallback: manual intervention if monitoring is down

---

## When to Use Cell Architecture

| Scenario | Cell Architecture? | Reason |
|----------|------------------|--------|
| 50M daily users, 3 continents | YES | Regional failure isolation, reduced blast radius |
| 1M daily users, single region | NO | Overhead not justified; simpler to replicate within one region |
| Multi-tenant SaaS, 100 customers | MAYBE | If you need complete failure isolation per customer; use if one customer's issues must not affect others |
| Search system, global index | NO | Cross-cell consistency too expensive; use sharding within a region |
| Payment system, 5 datacenters | YES | Each datacenter is a cell; failure of one doesn't block others |
| Microservice mesh, one cloud | NO | Use bulkheads within the mesh; cells are for infrastructure scale |

---

## Failure Scenarios: When Blast Radius Is Bounded

### Scenario A: Cascading Failure in One Cell

```
Cell-1: Slow database
  → API timeout (5s)
  → Circuit breaker opens
  → Requests fail fast
  
Blast radius:
  Cell-1: ~30% error rate (5s timeout, then circuit opens)
  Cell-2, Cell-3: 0% impact
  
Global effect:
  Capacity available from Cells 2 & 3
  Traffic reroutes
  Overall system: ~10% error rate (if Cell-1 is 33% of capacity)
```

### Scenario B: Deployment Bug in One Cell

```
New code deployed to Cell-1
  Introduces race condition in caching layer
  
Symptom:
  Cell-1 latency spikes (200ms vs normal 50ms)
  Error rate in Cell-1 increases slightly (stale cache hits)
  
Blast radius:
  Cell-1: degraded
  Cells 2 & 3: unaffected
  
Rollback:
  Revert deployment in Cell-1 only
  Cell-1 recovers in 1 minute
  Other cells continue serving traffic
  
Cost:
  If Cell-1 is 10% of traffic, impact is ~10% of users for ~1 minute
  If Cell-1 goes down, impact is ~10% of users + ~5 minute recovery
```

### Scenario C: Network Partition

```
US-EAST cell partitioned from rest of network
  Can't reach US-WEST, EU cells
  Can't reach central DNS authority
  
What happens:
  1. US-EAST cell detects partition (health check to central DNS fails)
  2. Cell marks itself "read-only mode" or "local-only"
  3. Existing US-EAST users continue (local reads/writes)
  4. New traffic routed away (global DNS still points to other cells)
  5. When partition heals, US-EAST rejoins
  6. Replication catches up (asynchronous)
  
Blast radius:
  US-EAST: Stale data until partition heals
  Other cells: No impact (already rerouted)
```

---

## Interview Q&A

**Recall 1:** What does "cell" mean in a cell architecture?

*Must-say:*
- A cell is a complete, independent replica of the system serving a geographic region or tenant.
- Each cell has data tier, service tier, control plane.
- Failures in one cell are contained (don't cascade to others).

**Probe 1:** You have 3 cells. Cell-1 goes down. How many users are affected?

*Expected:*
- Roughly 1/3 of users (assuming equal traffic split).
- Those users see connection errors / timeouts.
- Clients reconnect to Cell-2 or Cell-3 (DNS updates in ~10-30 seconds).
- After ~5 minutes, most users have reconnected.
- Cost: 1/3 of users for ~5 minutes (acceptable for a cascading system failure).

**Probe 2:** Cell-1 and Cell-2 disagree on the state of data (e.g., user's balance). Why?

*Expected:*
- Replication is asynchronous.
- User updates in Cell-1.
- Takes time to replicate to Cell-2.
- If user immediately reconnects to Cell-2, they see old data (stale read).
- Acceptable: eventual consistency, not strong consistency.
- If strong consistency needed: must route all writes through one cell (lower availability).

**Numeric 1:** You have 3 cells, each serving 1000 users. Cell-1 can handle 1500 users (150% capacity). Cell-1 fails. Can the remaining 2 cells absorb the traffic?

*Working:*
- Cell-2 + Cell-3 capacity: 2000 users
- Incoming traffic: 1000 users from Cell-1 (all at once if instant failover)
- 1000 < 2000, so yes, can absorb
- But if you designed each cell for 100% traffic (no buffer), overflow happens
- Answer: Yes, if each cell is designed for 150% capacity

**Numeric 2:** Cell-1 is degraded (2x latency). It serves 500 req/s normally. Clients timeout after 10s. How many requests are stuck?

*Working:*
- Normal latency: ~100ms
- Degraded latency: ~200ms
- Timeout: 10s
- Requests in flight: 500 req/s * 200ms = 100 requests
- Requests completed: 500 / 10 = 50 req/s (fewer complete in 10s due to slowness)
- Stuck requests: 500 * 10s = 5000 requests accumulated before timeout kicks in
- Answer: ~5000 requests timeout (all fail)

---

## Checklist: Implementing Cell Architecture

- [ ] **Design cells by geographic region or tenant.** Not per-service (cells should be complete stacks).
- [ ] **Each cell has independent data storage.** Don't share databases; replicate asynchronously.
- [ ] **Each cell has independent control plane.** Own scheduler, config, deployment system.
- [ ] **Health checks between cells are frequent and quorum-based.** Don't fail on a single bad check.
- [ ] **Capacity per cell handles ~150% of normal load.** So one cell failure is absorbable.
- [ ] **Data replication uses logical clocks or timestamps.** Prevent write-order conflicts.
- [ ] **Clients are aware of cell affinity.** Try local cell first, failover to others (DNS-driven).
- [ ] **Rollback at cell level is fast.** Redeploy to a single cell in <5 minutes.

### Common Wrong Answers

- "I'll have one global database; cells are just compute." ← No, defeats isolation.
- "Cells share a control plane." ← No, defeats failure isolation.
- "I'll replicate synchronously for strong consistency." ← Too slow, defeats the point.
- "Cells are just load-balanced servers." ← No, cells include storage, control, monitoring.

---

## Story Card: AWS Region Failure Handling

**Context:** AWS serves global customers. US-EAST-1 is the largest region. 2023 incident: power issue in one availability zone.

**Scenario:**
```
One AZ in US-EAST-1 experiences power loss.
  If system treats entire US-EAST-1 as one cell:
    → US-EAST-1 cell affected
    → Traffic reroutes to US-WEST-2, EU-WEST-1
    → Customers see degradation or errors
    
If system shards across AZs within US-EAST-1:
    → Only 1/3 of US-EAST-1 affected
    → Other AZs in US-EAST-1 absorb traffic
    → Customers in US-EAST see latency spike, not outage
```

**Lesson:** Cell architecture needs multiple layers (geographic cell, AZ cell within cell).

---

## References and Further Study

- **Designing Data-Intensive Applications** (Kleppmann): Cell architecture in cloud systems.
- **Netflix Architecture**: multi-region, cell-based design.
- **AWS Well-Architected Framework**: Multi-AZ, multi-region resilience patterns.
- **Patterns of Distributed Systems** (Narayan): Leader-follower replication, quorum, eventual consistency.
