# Multi-Tenancy & Noisy Neighbors: Isolation, Resource Contention, SLAs

## Why This Interview Matters

If you're building a multi-tenant platform (Stripe, Twilio, AWS, Datadog), you must isolate tenants. One tenant's spike in traffic shouldn't degrade others' performance. This is **critical for SaaS infrastructure interviews** and systems design.

**Core insight:** Shared resources without limits = one tenant can cause cascading failure for all tenants. Solving this is systems engineering.

---

## First Principle: The Noisy Neighbor Problem

Imagine a shared server with multiple tenants:

```
Shared compute:
  CPU: 8 cores, 16 GB RAM
  
Tenant A: 4 cores, 8 GB RAM normally
Tenant B: 2 cores, 4 GB RAM normally
Tenant C: 2 cores, 4 GB RAM normally

All running fine at ~50% utilization.
```

**Then Tenant A spikes (DDoS attack, sudden traffic spike, runaway query):**

```
Tenant A wants: 8 cores, 12 GB RAM
  → Consumes all available resources
  
Tenant B now gets:
  - 0.5 cores (starved)
  - 2 GB RAM (swapping to disk, OOM risks)
  - Latency spikes 10x
  - Error rate increases
  - SLA violated
  
Tenant C same problem as B
```

**Customer perspectives:**
- Tenant A: "Great, I'm getting max resources!"
- Tenant B: "System is slow! Why is my latency 10x?" (doesn't know about Tenant A)
- Tenant C: "System is broken! I'm getting timeouts!" (doesn't know about Tenant A)
- You (platform owner): "Three tickets, but it's just one noisy neighbor spike."

---

## Noisy Neighbor Scenarios

### Scenario 1: Runaway Query

Tenant A accidentally runs a query that scans 1 billion rows:

```
SELECT * FROM events WHERE created_at > '2020-01-01'
  -- No index on created_at
  -- Table scan: 1 billion rows
  -- Takes 1 hour, locks database, blocks other tenants
```

**Effect on system:**
- Database CPU: 100% (all on Tenant A's query)
- Tenant B queries: Timeout (queued behind Tenant A)
- Tenant C queries: Timeout (queued)
- Shared connection pool: Full (all connections waiting for Tenant A query)
- Platform error rate: 50%+ (Tenants B & C)

### Scenario 2: Cache Thrashing

Tenant A's dataset is 10x larger than cache:

```
Cache size: 1 GB
Tenant A dataset: 10 GB

Tenant A keeps accessing random parts of its dataset.
Each access misses cache (cache miss rate: 90%).
Cache fills with Tenant A's data.
Tenants B & C data evicted from cache.
Tenant B & C cache hit rate drops 80% → 5%.
```

**Effect:**
- Tenant A: Fine (cache working, even with misses)
- Tenant B & C: Latency increases 10x (hitting disk instead of cache)
- SLA violations for Tenants B & C

### Scenario 3: Network Bandwidth Spike

Tenant A downloads a large report (100 GB):

```
Shared network: 1 Gbps
Tenant A needs: 800 Mbps
Remaining: 200 Mbps
Tenants B & C: Must share 200 Mbps (normally ~400 Mbps each)
```

**Effect:**
- Tenant A: Gets bandwidth (90 seconds to download)
- Tenant B & C: Latency increases, requests stall waiting for network

---

## Isolation Mechanisms

### Mechanism 1: Resource Quotas (Hard Limits)

Assign fixed resources per tenant, never exceed:

```cpp
struct TenantQuota {
  max_cpu_percent: 25,        // 25% of 8 cores = 2 cores
  max_memory_gb: 4,           // 4 GB RAM
  max_connections: 100,       // DB connections
  max_qps: 1000,              // Queries per second
  max_bandwidth_mbps: 100,    // Network bandwidth
};

// Enforcement
void execute_request(request, tenant_id) {
  if (tenant_usage[tenant_id].cpu > quota[tenant_id].max_cpu) {
    reject(request, "quota exceeded");  // Fail fast
  }
  if (tenant_usage[tenant_id].qps > quota[tenant_id].max_qps) {
    throttle(request);  // Rate limit
  }
  // etc.
}
```

**Effect:**
- Tenant A spike: Hits quota limit, new requests rejected or throttled
- Tenant B & C: Unaffected (reserved quota protects them)
- Tradeoff: Tenant A gets error / degradation, but platform is stable

**Cost:**
- Need to estimate quota per tenant (too low = false rejections, too high = quota wasted)

### Mechanism 2: Reservation (Minimum Guarantee)

Reserve resources per tenant. Excess resources shared:

```
8 cores total

Tenant A reservation: 2 cores (minimum guarantee)
Tenant B reservation: 2 cores
Tenant C reservation: 2 cores
Reserved total: 6 cores

Unallocated: 2 cores (can be used by any tenant if they need more)

Normal operation:
  A uses 2, B uses 2, C uses 2 → all good
  
Tenant A spikes to 3 cores:
  A gets 3 (using 1 of the 2 unallocated)
  B still gets 2 (protected)
  C gets 1 (unallocated - 1)
  
Both B and C protected; A gets extra if available.
```

**Implementation:**
```cpp
struct TenantReservation {
  tenant_id: string,
  min_cpu: 2,     // Guaranteed
  max_cpu: 4,     // Can burst if available
};

void allocate_resources(tenant_id) {
  guarantee = reservation[tenant_id].min_cpu;
  burst_pool = total_available - sum(all_guarantees);
  
  additional = min(burst_pool, (reservation[tenant_id].max_cpu - guarantee));
  total_allocation = guarantee + additional;
  
  return total_allocation;
}
```

### Mechanism 3: Separate Infrastructure per Tenant

Extreme isolation: Each tenant gets its own database, cache, compute:

```
Tenant A: Dedicated pod (2 cores, 2 GB RAM, local DB)
Tenant B: Dedicated pod (2 cores, 2 GB RAM, local DB)
Tenant C: Dedicated pod (2 cores, 2 GB RAM, local DB)

Cost: 3x infrastructure cost
Benefit: Complete isolation (Tenant A spike = Tenant A only)
```

**When to use:**
- High-value tenants (each worth $100K+ ARR)
- Requires extreme isolation (security, compliance)

### Mechanism 4: Fair-share Scheduling (Proportion-based)

Share excess resources fairly:

```
Tenant A request rate: 2000 req/s (exceeds quota)
Tenant B request rate: 1000 req/s (within quota)
Tenant C request rate: 1000 req/s (within quota)

Total excess: 1000 req/s over quota
System capacity: 4000 req/s

Allocation:
  A quota: 1000 req/s (hard limit)
  B quota: 1000 req/s (hard limit)
  C quota: 1000 req/s (hard limit)
  Excess: 1000 req/s available
  
  Fair share excess: Each tenant gets 1/3 of excess
  A gets: 1000 + 333 = 1333 req/s
  B gets: 1000 + 333 = 1333 req/s (if B wants it)
  C gets: 1000 + 333 = 1333 req/s (if C wants it)
```

**Effect:**
- Tenants at quota don't starve
- Excess is shared proportionally
- No tenant can monopolize

---

## SLA Guarantees with Multi-Tenancy

An SLA (Service Level Agreement) is a promise:

```
Stripe SLA for processing payments:
  Latency: p99 < 100ms
  Availability: 99.99% uptime
  
If you share infrastructure:
  Tenant A spike → Tenant B latency increases → Stripe's SLA broken
  
How to maintain SLA despite multi-tenancy?
  Reserve enough capacity per tenant to deliver SLA
```

**SLA calculation:**

```
Target SLA:
  p99 latency < 100ms
  
Tenant A normal load: 1000 req/s, p99 latency 20ms
Tenant A peak load: 5000 req/s, p99 latency 80ms

Reserve capacity:
  Need to handle peak load (5000 req/s) with latency < 100ms
  = 2.5x normal capacity reserved
  
Cost: Over-provisioning for the spike
  
Multi-tenant tradeoff:
  If all tenants peak simultaneously, system overloaded
  Acceptable: SLA requires 99.99% uptime, but peaks are rare
  Only 1% of time is system overloaded (or less)
```

**Tenant tiers and SLAs:**

```
Free tier: 
  p99 latency: < 1000ms (best effort)
  Availability: 95%
  Resources: 1 shared pool (no isolation)
  
Pro tier:
  p99 latency: < 200ms (guaranteed)
  Availability: 99%
  Resources: Reserved pool
  
Enterprise tier:
  p99 latency: < 100ms (guaranteed)
  Availability: 99.99%
  Resources: Dedicated infrastructure
```

---

## Monitoring & Detection: Noisy Neighbor

How do you detect Tenant A is causing the problem?

```
System metrics:
  p99 latency: 500ms (was 50ms) ← Alert: latency spike
  Error rate: 5% (was <0.1%) ← Alert: errors spiking
  
Tenant-level metrics:
  Tenant A: 5000 req/s, p99 500ms, 0% error ← NOT the problem
  Tenant B: 100 req/s, p99 500ms, 5% error ← Experiencing degradation
  Tenant C: 100 req/s, p99 500ms, 5% error ← Experiencing degradation
  
Root cause: Tenant A's high request rate
  Tenant A normal: 1000 req/s
  Tenant A spike: 5000 req/s (5x spike)
  
Tenant A is noisy neighbor
```

**Monitoring setup:**

```
Per-tenant dashboard:
  - Request rate over time
  - Latency (p50, p99, p99.9)
  - Error rate
  - Resource usage (CPU, memory, connections)
  - Quota status (% of quota used)

Global dashboard:
  - System latency
  - System error rate
  - Resource utilization by tenant
  - SLA compliance per tenant
  
Alerting:
  - Quota exceeded: "Tenant A exceeded max_qps"
  - Noisy neighbor: "Tenant A using 90% of shared pool"
  - SLA breach: "Tenant B p99 latency exceeded"
```

---

## Architecture Patterns for Multi-Tenancy

### Pattern 1: Single Database, Row-level Isolation

```
One database for all tenants.
Data includes tenant_id.
Queries filtered by tenant_id:

SELECT * FROM events 
WHERE tenant_id = 'A' AND created_at > '2024-01-01'
```

**Pros:** Shared infrastructure, simple
**Cons:** Queries can accidentally fetch other tenants' data (security bug), one noisy query affects all

### Pattern 2: Schema-per-Tenant

```
Database has separate schemas:
  - schema_tenant_a
  - schema_tenant_b
  - schema_tenant_c
  
Each schema has its own tables.
```

**Pros:** Better isolation, queries don't need tenant_id filter
**Cons:** More storage, harder to share data, more complex management

### Pattern 3: Database-per-Tenant

```
Separate database per tenant:
  - db_tenant_a.stripe.com
  - db_tenant_b.stripe.com
  - db_tenant_c.stripe.com
```

**Pros:** Maximum isolation, can shard per-tenant
**Cons:** Highest infrastructure cost, complex global queries

### Pattern 4: Hybrid (Tiered)

```
Free tier: Shared database + row-level isolation
Pro tier: Schema per 10 tenants
Enterprise tier: Dedicated database per tenant
```

**Pros:** Cost scales with value, maintains isolation where needed
**Cons:** Operational complexity

---

## When to Isolate vs Share

| Scenario | Share | Isolate | Reason |
|----------|-------|---------|--------|
| Free tier users (100s of them) | YES | N/A | Cost-prohibitive to isolate |
| Enterprise customer ($1M ARR) | NO | YES | Worth dedicated resources |
| Compliance requirement (PCI-DSS) | NO | YES | Legal requirement |
| Unpredictable traffic spikes | NO | YES | Isolation protects others |
| High-value customers in free tier | NO | YES | Risk of SLA breach > cost |
| Read-heavy workload (low contention) | YES | N/A | Low risk of noisy neighbor |
| Write-heavy workload (contention) | NO | YES | High risk of lock contention |

---

## Interview Q&A

**Recall 1:** What is a noisy neighbor? Why is it a problem?

*Must-say:*
- A noisy neighbor is a tenant consuming more than its fair share of resources.
- It causes other tenants' latency to increase and errors to spike.
- Solution: Resource quotas, reservations, or isolation.

**Probe 1:** Tenant A uses 5x normal CPU. How do you prevent it from affecting Tenant B?

*Expected:*
- Option 1: Hard quota (Tenant A rejected or throttled once it exceeds 25% CPU)
- Option 2: Reservation (Tenant B guaranteed 2 cores minimum)
- Option 3: Separate infrastructure (Tenant A and B on different servers)
- Any one is acceptable; all three is ideal.

**Probe 2:** Database query from Tenant A scans 1 billion rows. How do you stop it from locking out Tenant B's queries?

*Expected:*
- Query timeout (kill long-running queries after 30s)
- Query admission control (don't allow queries that would scan > X rows)
- Separate connection pools per tenant
- Priority-based execution (Tenant B's queries prioritized over Tenant A's)

**Numeric 1:** System has 8 cores. Tenant A quota: 25%, Tenant B: 25%, Tenant C: 25%, Reserved excess: 25%. Tenant A spikes to use 6 cores. How many cores does Tenant B get?

*Working:*
- Tenant A quota: 8 * 0.25 = 2 cores
- Tenant B quota: 8 * 0.25 = 2 cores
- Tenant C quota: 8 * 0.25 = 2 cores
- Reserved excess: 8 * 0.25 = 2 cores
- Tenant A: wants 6, quota allows 2 (can burst into reserved 2), but can't exceed 4 (quota + shared)
- Tenant A gets: 4 cores (2 quota + 2 shared)
- Tenant B gets: 2 cores (its quota, protected)
- Tenant C gets: 2 cores (its quota, protected)
- Answer: 2 cores (fully protected by quota)

**Numeric 2:** Tenant A runs 10,000 queries/sec. Processing time per query: 10ms. Shared CPU can do 500 queries/sec. How long before errors occur?

*Working:*
- Incoming: 10,000 queries/sec
- Throughput: 500 queries/sec
- Queue growth: 10,000 - 500 = 9,500 queries accumulate per second
- Queue timeout: 10 seconds (typical)
- Errors start: 10 * 9,500 = 95,000 queries timeout after 10s
- Answer: Errors occur within ~1 second (queue fills up fast)

---

## Checklist: Multi-Tenant Isolation

- [ ] **Define resource quotas per tenant tier.** Free = shared, Pro = reserved, Enterprise = dedicated.
- [ ] **Enforce quotas at request entry point.** Not at database (too late). Rate limit / reject early.
- [ ] **Monitor per-tenant resource usage.** Can you spot Tenant A is the noisy neighbor?
- [ ] **Implement circuit breaker per tenant.** If Tenant A exceeds quota, fail its requests (not others).
- [ ] **Use separate connection pools or circuits per tenant.** Prevents one tenant's exhaustion.
- [ ] **Set query timeouts.** Runaway queries don't lock database.
- [ ] **Guarantee minimum resources to each tenant.** Reservation, not just quota.
- [ ] **Document SLA per tier.** What latency / availability does each tier get?
- [ ] **Test cascade scenarios.** Tenant spikes, verify others unaffected.

### Common Wrong Answers

- "I'll just scale up if one tenant spikes." ← No, scaling takes minutes; noisy neighbor impacts are immediate.
- "I'll put everything in a shared database and hope no one is noisy." ← Naive; will fail in production.
- "I'll isolate storage, not compute." ← Incomplete; noisy compute affects other tenants' latency.
- "I'll use SLA targets but no actual enforcement." ← No; targets without enforcement = false promises.

---

## Story Card: Stripe Payment Processing During Fraud Storm

**Context:** Stripe processes payments globally. One day, a wave of high-frequency fraud tests hit.

**Scenario:**
```
Attacker tests 100K card numbers in parallel.
Each test: POST /v1/charges with card number.

Without isolation:
  Fraud attempts: 100K req/s
  Normal payment traffic: 10K req/s
  Total: 110K req/s
  System capacity: 50K req/s
  
  Result: Both fraud and legitimate payments degraded.
  Legitimate merchants see errors.
  SLA broken for all.

With isolation (quota per IP, tenant, or customer):
  Fraud IP: Quota 100 req/s
  Fraud requests: 100K req/s → throttled to 100 req/s
  Normal traffic: 10K req/s → all pass through
  
  Result: Fraud attempts absorbed, legitimate payments unaffected.
  SLA maintained.
```

**Lesson:** Without multi-tenant isolation, one attacker can break the platform for everyone.

---

## Further Study

- **Google Borg**: Cluster manager handling multi-tenancy at scale.
- **Microservices Patterns**: Tenant isolation patterns.
- **Designing Data-Intensive Applications**: Sharding, scaling, resource allocation.
