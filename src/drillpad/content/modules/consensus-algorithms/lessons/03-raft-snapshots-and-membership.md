# Raft Snapshots, Log Compaction & Membership Changes

## The Problem

Your Raft cluster has been running for 6 months. The log is 10 GB. A new server joins the cluster. You replay 10 GB of logs to catch it up. Takes 2 hours. During that time, the new server can't vote, so quorum is reduced. If another server crashes, you lose fault tolerance.

```
Scenario: etcd cluster grows from 3 to 5 nodes

Node A: ~10 GB log (6 months of entries)
Node B: ~10 GB log
Node C: ~10 GB log

Node D (new): joins cluster
  Problem: Need to replicate 10 GB log to Node D
  Latency: ~2 hours @ 1.5 MB/sec
  
During catch-up:
  Active nodes: A, B, C (need 2 for quorum, have 3, OK)
  If Node A crashes: active = B, C (need 2, have 2, OK)
  If Node B crashes: active = C, D (need 2, have 1 + new, risky)
  
  System is fragile until D fully caught up
```

**Why this matters:** Snapshots are essential for scaling Raft to production systems handling millions of requests. Without snapshots, new nodes take hours to join. With snapshots, minutes.

---

## First Principles: Why Snapshots Matter

Raft log is the source of truth. But keeping 10 years of log is impractical.

```
Old approach: Replay all log entries
  10 GB log × 50 MB/sec throughput = 200 seconds
  If node processes complex business logic per entry: 10x slower
  New node unusable for 30 minutes

Snapshot approach: Save state at a point in time
  Snapshot @ entry 1,000,000: "The state at this log index"
  Keep only recent entries (last 100,000)
  Total size: 500 MB snapshot + 100 MB log = 600 MB
  Time to replicate: ~10 seconds
```

---

## Snapshot Anatomy

A snapshot contains:

```
Snapshot {
  last_included_index: 1,000,000
  last_included_term: 42
  last_config: {nodes: [A, B, C]}
  state_machine: <serialized application state>
}

// Example: Key-value store snapshot
Snapshot {
  last_included_index: 1,000,000
  state_machine: {
    "key1": "value1",
    "key2": "value2",
    ...
    "key_1000000": "value_1000000"
  }
}
```

**Workflow:**

```
Timeline of Raft node:

t=0: Startup
  Load snapshot (entry 0, empty state)
  
t=1-1000000: Apply log entries
  Entry 1: SET key1=value1 (apply to state)
  Entry 2: SET key2=value2
  ...
  Entry 1000000: SET key_1000000=value_1000000
  
  Snapshot size: 500 MB (storing 1M entries)
  Log size: 10 GB (all 1M entries)

t=1000000: Create snapshot
  Save state to disk
  Snapshot file: "snapshot_1000000_term42.bin"
  size: 500 MB
  
t=1000001-1000100000: Continue log
  Keep entries 1000000-1000100 in memory (recent 100 entries)
  Discard entries 1-999999 (already in snapshot)
  
  Log size now: 100 MB (instead of 10 GB)

t=1000100: Create another snapshot
  Snapshot file: "snapshot_1000100_term42.bin"
  Discard old snapshot, keep latest

Result: Log size stays ~100 MB (bounded by snapshot interval)
```

**Diagram: Snapshot in Log**

```
Log entries and snapshots:

Entries:  [1] [2] [3] ... [1M] [1M+1] ... [1M+100K]
           ↑                    ↑
           Snapshot @ 1M        Recent entries
           
Snapshot captures state @ entry 1M
Recent entries 1M-1M+100K stay in log
Old entries 1-1M are discarded

When new node joins:
  Option A (no snapshot): Replicate all 1M entries (slow)
  Option B (with snapshot): Send snapshot (fast) + recent entries (fast)
```

---

## Membership Changes (Dynamic Configuration)

Adding/removing nodes to Raft cluster is tricky. You can't just add a node to the membership list and commit.

```
Problem: Split-brain risk

Old config: A, B, C (quorum = 2)
Desired: A, B, C, D, E (quorum = 3)

Naive approach: Update config in one log entry
  Entry N: {config: [A, B, C, D, E]}
  
  Risk:
    If majority disagree about new config:
    Subset: A, B agree on new config [A, B, C, D, E]
    Subset: C disagrees, keeps old [A, B, C]
    
    Now we have two quorums!
    A+B (with D, E) and C can both commit entries
    Split-brain
```

**Solution: Two-Phase Membership Change (Joint Consensus)**

```
Step 1: Enter transitional state (C_old,new)
  Entry N: {config: [A, B, C] + [D, E]}
           (both old and new members)
  
  Quorum now = max(quorum_old, quorum_new)
  = max(2, 3) = 3 votes needed
  
  This requires majority of BOTH old and new configs!
  (A, B, C, D) → A, B, D must agree
  (A, B, C, E) → A, B, E must agree
  But not (D, E, A) alone

Step 2: Wait for entry N to be committed
  Once committed, all old+new nodes know the transition
  
Step 3: Apply final config
  Entry N+1: {config: [A, B, C, D, E]}
  Quorum = 3 (only new members matter)
  
  Now (D, E, A) CAN form a majority (3 of 5)
```

**Diagram: Safe Membership Change**

```
Phase 1: Transitional (joint) config

  Old majority: A, B, C (need 2)
  New majority: A, B, C, D, E (need 3)
  Joint majority: need to agree with BOTH
  
  A, B agree → majority of old (2 of 3)
  A, B, D agree → majority of new (3 of 5)
  
  Both are satisfied!
  
  This prevents split-brain: can't form new cluster of only [D, E]
  (D, E alone don't form new majority of 3)

Phase 2: Final config

  Only new members matter: [A, B, C, D, E]
  D, E, A can form majority (3 of 5)
```

---

## Failure Scenario: Snapshot Corruption

```
Node A creates snapshot at entry 100,000
  Writes to disk: "snapshot_100000.bin"
  
Node B joins cluster, requests snapshot
  Node A sends snapshot over network
  Corruption during transfer (cosmic ray bit flip)
  
Node B receives corrupted snapshot
  Applies bad state to state machine
  Commits entries based on corrupted state
  
Result: Node B has permanently wrong state
  All future entries built on wrong foundation
  
Detection:
  - Checksum validation (CRC32 of snapshot)
  - Compare state across nodes (periodic audit)
  - Monitor divergence in queries
```

**Prevention:**
- CRC32 checksum on snapshot files
- Verify checksum during transfer
- Verify checksum after receiving
- Monitor for state divergence

---

## Raft vs Paxos: Tradeoffs

```
               Raft                Paxos
Understandability  Simpler        Complex (3 phases)
                   Single leader  Multiple leaders possible

Implementation    Easier          Harder
                  Fewer edge cases More edge cases

Leader failure     Quick recovery  Slower (multi-phase)
                   New leader      No built-in leader

Membership         2-phase         Complex
                   Well-defined    Less clear

Log replication    Simple          Complex
                   Append-only     Proposals & promises

Network partition  Split-brain     Multiple quorums
                   Prevented       Can diverge

Explanation        "Draw a picture" "Listen to PhD thesis"
```

**When to use Raft:**
- Building new system (etcd, Consul)
- Need simple, understandable consensus
- Want built-in leader election
- Can afford to restart failed processes

**When to use Paxos:**
- Leaderless system (Google Chubby, Zookeeper)
- Byzantine failures (rare in data center)
- Need tolerance for simultaneous failures
- Can afford complexity

---

## Interview Pattern: Cluster Growing Pains

```
Q: "Your Raft cluster (3 nodes, 5 GB log) grows to 7 nodes.
   New nodes take 30 minutes to catch up.
   During that time, you lose one node, quorum drops to 3/7 = below 50%.
   Your service goes read-only for 10 minutes.
   How would you fix this?"

Weak answer:
  "Just add the nodes faster"
  (❌ Not actionable, network bandwidth is the limit)
  
  Or: "Use snapshots"
  (✓ Correct, but missing details)

Strong answer:
  "Root cause: Replicating full log is too slow.
   
  Solution: Snapshots
   
   1. How snapshots work:
      - Periodically save application state to disk
      - Keep recent log entries (~100K entries)
      - Old entries discarded (already in snapshot)
   
   2. Implementation:
      a) On existing nodes: Create snapshot every 10K entries
         - Snapshot size: 500 MB (vs 5 GB log)
         
      b) When new node joins:
         - Send snapshot (500 MB) + recent log (100 MB)
         - Total: 600 MB
         - Time: 600MB / 50MB per sec = 12 seconds
         - (vs 30 minutes for full log)
      
      c) New node applies snapshot + log entries quickly
      
   3. Quorum impact:
      - With 12s catch-up: new nodes join quickly
      - Quorum restored rapidly
      - If node fails, still have 7 for quorum
   
   4. Edge cases:
      - What if snapshot is corrupted? (checksum validation)
      - What if new node crashes during catch-up? (retry)
      - What if snapshot is huge (100 GB)? 
        (Use incremental snapshots or partition by range)
   
   5. Rollout:
      - Add snapshot creation to leader
      - Canary with 1 new node
      - Monitor: catch-up time, CPU, disk IO
      - Then add remaining nodes
   
   Why this works:
   - Snapshots are standard in production Raft
   - Scales to any log size
   - Reduces catch-up time from hours to seconds
   
   Trade-off:
   - Adds complexity (snapshot creation/transfer)
   - Uses more disk IO (write snapshot to disk)
   - But worth it for reliability"

Why this signals good judgment:
  - You understand why snapshots are needed
  - You know snapshot transfer is still bottleneck
  - You think about checksum/correctness
  - You consider edge cases (corruption, huge snapshots)
  - You have a measurable metric (catch-up time)
  - You rollout cautiously (canary)
```

---

## Checklist: Raft Production Deployment

- [ ] Snapshots enabled (interval: ~10K-100K entries)
- [ ] Snapshot checksum validated (CRC32)
- [ ] Snapshot size bounded (alert if > threshold)
- [ ] Membership changes use 2-phase (joint consensus)
- [ ] Leader elected in < 5 seconds (election timeout tuned)
- [ ] Log replication latency monitored (p99 < 100ms)
- [ ] Catch-up time for new nodes measured (< 5 minutes)
- [ ] Quorum always maintained (monitoring)
- [ ] Disk space for log + snapshots provisioned (1.5x log size)

## Common Wrong Answers

1. **"Just disable snapshotting, keep full log"**
   - Log grows unbounded
   - New nodes take hours
   - Restart time hours

2. **"Add nodes one at a time to avoid quorum loss"**
   - Slow and risky
   - Better: snapshots + parallel add

3. **"Use Paxos instead because Raft is too simple"**
   - Raft is proven in production (etcd, Consul)
   - Paxos is more complex, not better for this problem

4. **"Just commit the new config in one entry"**
   - Split-brain risk
   - Two-phase (joint consensus) is required

5. **"Snapshots don't need checksums"**
   - Network/disk corruption happens
   - Even 1-bit flip causes state divergence
   - Always verify snapshots
