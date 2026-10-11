# Infrastructure Primitive: Distributed Lock & Coordination

## Firm Archetype: Zookeeper, etcd, Consul, Google Chubby architects

**Problem:** Coordinate N machines. Elect a leader, distribute work, prevent split-brain, ensure exactly-once semantics.

**Why hard:** Asynchronous networks (no bounds on message delay), partial failures (some nodes down), Byzantine failures (lying nodes), deadlock risks.

---

## Single-Machine Locks (Baseline)

```
Mutual exclusion (single machine):
  
  Critical section:
    ├─ Only one thread can execute
    ├─ Lock: acquire before entry
    ├─ Unlock: release after exit
  
  Mechanism:
    ├─ Semaphore: binary (0=unlocked, 1=locked)
    ├─ Mutex: lock + queue
    └─ Atomic compare-and-swap (CAS)
  
  Example (Python):
    lock = threading.Lock()
    with lock:
        # critical section (only one thread here)
        shared_counter += 1

Works because:
  ├─ Shared memory (no network delay)
  ├─ One machine enforces atomicity
  └─ Trivial: one lock holder at a time
```

### Scaling to Distributed Systems

```
Problem: shared memory is local to one machine

Solution 1: Pessimistic (strong locks)
  ├─ Acquire lock from central server
  ├─ Guarantee: only one holder globally
  ├─ Failure: if lock server down, deadlock
  └─ Cost: lock server bottleneck

Solution 2: Optimistic (CAS + retry)
  ├─ Assume no conflict
  ├─ Execute operation
  ├─ Commit with compare-and-swap
  ├─ If conflict: retry
  └─ Cost: retry loop, complex

Solution 3: Leases (time-bounded locks)
  ├─ Lock expires after T seconds
  ├─ Prevent deadlock (stale lock auto-released)
  ├─ Must renew before expiry
  └─ Trade-off: lease window = recovery window
```

---

## Distributed Locking with Leases

### Simple Lease-Based Lock

```
Scenario: Two services (A, B) want to update shared config

Service A:
  1. Request lease: POST /lock {resource: "config", ttl: 10}
  2. Server returns: {lease_id: "abc123", expires_at: time + 10}
  3. A acquires lock (can update config)
  4. A updates config
  5. A releases lease: DELETE /lock/abc123

Service B (waiting):
  1. Request lease: POST /lock {resource: "config", ttl: 10}
  2. Server returns: 409 Conflict (A holds lease)
  3. B polls every 100ms
  4. When A's lease expires, B acquires new lease

Failure case (A crashes without releasing):
  ├─ A's lease expires after 10 sec
  ├─ B acquires lease automatically
  └─ No deadlock (time-bounded recovery)

Data structure (server):
  leases = {
    "config": {
      holder: "service_a",
      lease_id: "abc123",
      expires_at: 1609459210000
    }
  }
```

### Fencing Tokens (Prevent Stale Writers)

```
Problem: A acquires lease, updates database, crashes
         Server: thinks A failed, grants lease to B
         A: recovers, still thinks it holds lease, writes again
         Result: A and B both writing (corruption)

Solution: Fencing token

  Lease includes token:
    ├─ Lease V1: token = 1, holder = A
    ├─ Lease V2: token = 2, holder = B
    ├─ Token = monotonically increasing
  
  Database write:
    A: UPDATE config SET value = "new" WHERE fencing_token >= 1
       (A's token is 1, this write succeeds)
    
    B: UPDATE config SET value = "newer" WHERE fencing_token >= 2
       (B's token is 2, this write succeeds)
    
    A (stale): UPDATE config SET value = "old" WHERE fencing_token >= 1
       (A's token is 1, but database fencing_token = 2)
       (WHERE condition false, update doesn't apply)
  
  Result: B's write wins, A's stale write rejected

How to implement:
  ├─ Database: store last fencing_token per resource
  ├─ Condition: new_token > stored_token (not >=)
  ├─ Token given by lease server (monotonic)
  └─ Prevents: split-brain, stale writes
```

---

## Leader Election (Consensus-Based)

### Zookeeper-Style Election

```
Scenario: N servers (A, B, C), need one leader

Zookeeper sequence (ephemeral):
  ├─ Create ephemeral nodes: /election/candidate_1, _2, _3
  ├─ Wait for: all lower-numbered nodes to disappear
  ├─ When only you remain: you are leader
  
  Step-by-step:
    A: creates /election/candidate_1 (watch on _0)
    B: creates /election/candidate_2 (watch on _1)
    C: creates /election/candidate_3 (watch on _2)
    
    A: is candidate_1 is lowest? yes → A is leader
    B: watch on candidate_1, wait for it to disappear
    C: watch on candidate_2, wait for it to disappear
    
    A crashes:
    ├─ /election/candidate_1 disappears (ephemeral)
    ├─ B woken up (watched node gone)
    ├─ B checks: am I lowest? yes → B is leader
    └─ C watches B's node, waits

Advantages:
  ├─ No timing (no timeouts, just watches)
  ├─ Automatic recovery (crashed node removed)
  └─ Scalable (log N latency)
  
  Disadvantage:
  └─ Cascading failures (all others woken, contend for leader)
```

### Raft Consensus

```
Raft for leader election:

Terms:
  ├─ Each term has at most 1 leader
  ├─ Term = (logical time, votable)
  └─ Nodes: follower → candidate → leader

Election timeout:
  ├─ Follower: waits for heartbeat from leader
  ├─ If no heartbeat for 150-300ms: become candidate
  ├─ Candidate: request vote from all nodes
  ├─ Quorum: majority votes → become leader
  ├─ Leader: send heartbeat every 50ms

Example:
  Term 1:
    ├─ A elected leader (gets majority)
    └─ Sends heartbeat every 50ms
  
  A crashes:
    ├─ B, C: no heartbeat for 150-300ms
    ├─ B: become candidate, request votes
    ├─ C, A (dead) vote for B
    ├─ B: gets majority (2 of 3) → leader
    └─ Term 2: B is leader

Advantages:
  ├─ Automatic leader selection
  ├─ Recovers from single node failure
  ├─ Time-bounded (election within heartbeat period)
  
  Disadvantage:
  └─ Unavailable during election (50-300ms)
```

---

## Consensus Protocols (For Exactly-Once)

### Two-Phase Commit (2PC)

```
Goal: execute operation on multiple machines, all-or-nothing

Coordinator (C): transaction manager
Participants (P1, P2, P3): database nodes

Phase 1 (Prepare):
  1. C: "Prepare to commit {transfer $10 from A to B}"
  2. P1: lock rows, verify possible → vote "yes"
  3. P2: lock rows, verify possible → vote "yes"
  4. C: collects votes (must be unanimous)

Phase 2 (Commit):
  5. C: "Commit {transfer $10}"
  6. P1: apply change
  7. P2: apply change
  8. C: "Committed"

Atomicity guarantee:
  ├─ All succeed: transaction committed
  ├─ Any abort: transaction rolled back
  └─ No partial application

Problem: blocking
  ├─ Participants: hold locks during 2 phases
  ├─ If coordinator crashes in phase 2: deadlock
  ├─ Participants: stuck waiting (can't release locks)
  └─ Duration: minutes possible (bad)

When to use:
  ├─ Strong consistency required
  ├─ Short transactions only
  ├─ Low latency tolerance
```

### Saga Pattern (Long-Running Transactions)

```
Goal: exactly-once over multiple services (without blocking locks)

Choreography (event-driven):
  1. User: transfer $10 (A → B)
  2. Service A: debit A by $10, emit event "transfer_initiated"
  3. Service B: credit B by $10, emit event "transfer_completed"
  
  If B fails:
    ├─ Service A: watches for timeout
    ├─ Service A: emit "transfer_rollback"
    ├─ Service A: refund A by $10
    └─ No lock held (asynchronous)

Orchestration (coordinator):
  1. Coordinator: "Execute transfer A → B"
  2. Coordinator → A: "Debit by $10"
  3. A: applies, returns success
  4. Coordinator → B: "Credit by $10"
  5. B: applies, returns success
  6. Coordinator: "Saga complete"
  
  If B fails:
    ├─ Coordinator → A: "Rollback"
    ├─ A: refund by $10
    └─ Saga reverted

Advantages:
  ├─ No blocking locks
  ├─ Long-running transactions OK
  ├─ Asynchronous (high throughput)
  
  Disadvantages:
  ├─ Eventual consistency (intermediate states visible)
  ├─ Semantic rollback (can't undo refund if A itself crashes)
  └─ Complexity (rollback logic per service)

Exactly-once guarantee:
  ├─ Idempotent operations (safe to retry)
  ├─ Dedup on receiver (don't apply twice)
  ├─ Example: transfer with idempotency_id
  │  If A sends "transfer:id=123" twice, B applies once
```

---

## Code Example (Lease-Based Lock)

```python
import time
import uuid
from threading import Thread

class DistributedLockService:
    def __init__(self):
        self.leases = {}  # resource -> {holder, token, expires_at}
        self.tokens = 0
    
    def acquire_lease(self, resource, ttl=10):
        """Acquire lease for resource."""
        if resource in self.leases:
            lease = self.leases[resource]
            if time.time() < lease['expires_at']:
                # Lease held by someone
                return None
            # Lease expired, reclaim
        
        # Grant new lease
        self.tokens += 1
        token = self.tokens
        lease_id = str(uuid.uuid4())
        
        self.leases[resource] = {
            'holder': lease_id,
            'token': token,
            'expires_at': time.time() + ttl
        }
        
        return {
            'lease_id': lease_id,
            'token': token,
            'expires_at': time.time() + ttl
        }
    
    def release_lease(self, resource, lease_id):
        """Release lease."""
        if resource in self.leases:
            if self.leases[resource]['holder'] == lease_id:
                del self.leases[resource]
                return True
        return False
    
    def renew_lease(self, resource, lease_id, ttl=10):
        """Renew existing lease."""
        if resource in self.leases:
            if self.leases[resource]['holder'] == lease_id:
                self.leases[resource]['expires_at'] = time.time() + ttl
                return True
        return False

# Leader election example
class LeaderElection:
    def __init__(self, node_id):
        self.node_id = node_id
        self.is_leader = False
        self.term = 0
        self.voted_for = None
    
    def request_vote(self, candidate_id, candidate_term):
        """Handle vote request (Raft)."""
        if candidate_term > self.term:
            self.term = candidate_term
            self.voted_for = candidate_id
            return True  # Vote for candidate
        elif candidate_term == self.term:
            # Already voted in this term
            return self.voted_for == candidate_id
        else:
            return False  # Stale term
    
    def become_candidate(self):
        """Start election."""
        self.term += 1
        self.voted_for = self.node_id
        self.is_leader = False
        # In practice: broadcast vote requests to all nodes
        print(f"Node {self.node_id}: starting election for term {self.term}")
    
    def become_leader(self):
        """Win election."""
        self.is_leader = True
        print(f"Node {self.node_id}: became leader in term {self.term}")
```

---

## Interview Checklist

- [ ] Difference: local locks vs distributed locks
- [ ] Lease-based locks (time-bounded, auto-release)
- [ ] Fencing tokens (prevent stale writers)
- [ ] Leader election: Zookeeper vs Raft
- [ ] Consensus: 2PC vs Saga (blocking vs async)
- [ ] Exactly-once: idempotency + deduplication
- [ ] Failure modes: lock server down, network partition
- [ ] Timing: election timeout, lease TTL, heartbeat

## Common Wrong Answers

- ❌ "Use single lock server" — bottleneck, single point of failure
- ❌ "No fencing tokens" — stale writers cause corruption
- ❌ "Always use 2PC" — blocks for minutes, unscalable
- ❌ "Ignore lease expiry" — deadlock on crashed holder
- ❌ "No heartbeat" — leader crashes, no one detects for minutes
- ❌ "Shared memory locking" — doesn't work across machines
