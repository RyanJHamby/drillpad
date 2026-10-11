# Byzantine Failures: Silent Corruption, Replication Lag, Divergent State

## First Principle: You Can't Trust Everything

A **Byzantine failure** is when a component gives you **wrong data silently**. Not a crash (easy to detect), but **corruption** (hard to detect).

```
Normal failure (easy):
  Server crashes → connection refused → immediately know it's down

Byzantine failure (hard):
  Server returns incorrect data → looks normal → system uses bad data
  Payment system: "charge $100" → stored as "$1000" silently
  Order book: "buy 100 @ $101" → stored as "sell 100 @ $101" (flipped)
  Cache: returns stale data thinking it's fresh
```

**Sources of Byzantine failures:**
- Replication lag (secondary lags behind primary)
- Silent data corruption (bit flip, storage corruption)
- Logic bugs (race condition in update)
- Network packet corruption (cosmic rays, faulty hardware)

---

## Real Example: SiteWise ExternalId Uniqueness

**Setup:** AWS IoT SiteWise manages 100K+ IoT devices across accounts.

**Invariant:** Each device has unique ExternalId per customer account. Two devices in same account can't have same ExternalId.

**What can break:**

```
Scenario 1: Replication lag
  Primary DB: ExternalId "sensor-01" doesn't exist yet
  Customer A: Creates device with ExternalId "sensor-01" (writes to primary)
  Secondary DB (lagged): ExternalId "sensor-01" doesn't exist yet (hasn't replicated)
  Customer B (reads from secondary to check uniqueness): "sensor-01 is free!"
  Customer B: Creates device with ExternalId "sensor-01"
  
  Now: Two devices with same ExternalId in same account
  Invariant broken silently (customers don't notice immediately)

Scenario 2: Bit flip in storage
  Device 1 has ExternalId "abc123" stored as binary
  Storage: bit flip → becomes "abc223" (silent corruption)
  Uniqueness check: looks for "abc123", doesn't find "abc223" → allows duplicate
  Later: two devices appear to have same logical ID
```

---

## Detection: Audit Trail

**Without detection:**
- Two devices with same ExternalId exist
- Nobody notices until customer complains
- By then: 1000 hours of wrong data, hard to reconcile

**With detection:**
- Audit log every ExternalId write: (timestamp, account_id, device_id, external_id)
- Periodically scan: "Find duplicate ExternalIds in same account"
- If found: alert, investigate, correct

```
Audit log:
  2026-10-09 10:00:00 | account:123 | device:A | external_id:"sensor-01"
  2026-10-09 10:05:00 | account:123 | device:B | external_id:"sensor-01"  ← DUPLICATE!
  
  Root cause: Replication lag (log entry B came after A, but should have been rejected)
  Recovery: Delete device:B, alert customer
```

---

## Prevention: Checksums & Redundant Verification

```cpp
// Store checksum with data
struct Device {
  int device_id;
  string external_id;
  string account_id;
  
  // Checksum of important fields
  uint32_t checksum() {
    return hash(device_id, external_id, account_id);
  }
};

// On read, verify checksum matches
Device read_device(int id) {
  Device dev = db.read(id);
  if (dev.checksum() != compute_checksum(dev)) {
    log_error("Checksum mismatch, data corrupted");
    alert_monitoring();
  }
  return dev;
}

// On uniqueness check, query both primary and secondary
bool is_unique(string external_id, string account_id) {
  bool primary_unique = primary_db.check_unique(external_id, account_id);
  bool secondary_unique = secondary_db.check_unique(external_id, account_id);
  
  if (primary_unique != secondary_unique) {
    log_error("Replication lag: primary and secondary disagree");
    alert_monitoring();
    // Conservative: assume not unique
    return false;
  }
  
  return primary_unique;
}
```

---

## Consistency Models: The Trade-off

```
Strong consistency (safe but slow):
  Write to primary → wait for replicas to confirm → return
  Time: 50ms (wait for all replicas)
  Cost: throughput limited, latency high
  Guarantee: all readers see consistent data
  
Eventual consistency (fast but risky):
  Write to primary → return immediately
  Replicas catch up asynchronously (lag: 100ms–1s)
  Cost: fast, high throughput
  Risk: readers might see stale data temporarily
  
Causal consistency (middle ground):
  Write to primary → return
  Replicas see write in order (causality preserved)
  Readers see consistent causal history
  Lag: ~10ms, better throughput than strong
```

**SiteWise design choice:** Causal consistency
- Writes are causally ordered (if A writes X, then B writes Y, all readers see X before Y)
- But replication lag can cause Byzantine failures (secondary returns stale external_id)
- Mitigation: audit logs + periodic reconciliation

---

## Story Card: SiteWise ExternalId System

**Setup:** You built ExternalId system ensuring uniqueness across 100K+ devices, 10K+ accounts.

**Initial design:** Strong consistency (every write waits for replicas)
- Problem: 10M writes/day * 50ms latency = 139 hours of waiting per day
- Bottleneck: replication confirmation

**Redesign:** Causal consistency + audit + reconciliation
- Writes: return immediately (fast)
- Reads: always hit primary for uniqueness check (consistency)
- Audit: log every write for reconciliation
- Reconciliation: batch job finds divergence, corrects nightly

**Result:** (Resume claim: "cutting customer onboarding time 40%")
- Reduced latency: 50ms → 5ms (strong → causal)
- Fast device creation: 10x throughput improvement
- Onboarding: 40% faster (devices created faster, fewer manual checks needed)

**Key insight:** You can't have perfect consistency and high throughput. Choose causal consistency, then add audit trails to detect Byzantine failures.

---

## Q&A

**Recall 1:** What is a Byzantine failure? How is it different from a crash?

*Must-say:*
- Crash: easy to detect, connection fails
- Byzantine: silent data corruption, looks normal
- Replication lag, bit flips, logic bugs cause Byzantine failures

**Probe 1:** You have a uniqueness constraint. You use causal consistency with primary/secondary. How do you ensure the constraint isn't violated?

*Expected:*
- Always check uniqueness on primary (single source of truth)
- Secondary might be stale, so don't trust it for uniqueness
- If you must read from secondary, validate against primary before committing

**Numeric 1:** Replication lag is 500ms. You write ExternalId "abc" to primary. Secondary hasn't replicated yet. You read from secondary. Do you see "abc"?

*Working:*
- Write: primary has "abc"
- Read from secondary (immediately): no, lag is 500ms
- You think "abc" is free, create it
- 500ms later: replication catches up, now two devices with "abc"

---

## Questions for the Interviewer

- How do you detect Byzantine failures in your system? (audit logs, checksums?)
- What's your consistency model? (strong, causal, eventual?)
- How do you reconcile divergent state after a failure?
- Have you had a silent corruption bug? (what caused it?)
