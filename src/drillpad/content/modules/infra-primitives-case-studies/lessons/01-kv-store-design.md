# Infrastructure Primitive: Key-Value Store Design

## Firm Archetype: Redis, DynamoDB, Cassandra, Memcached architects

**Problem:** Design a distributed KV store. Store 1TB+ of data, serve 1M QPS with <10ms latency, survive node failures, handle geo-replication.

**Why hard:** Partitioning (hash vs range), replication (consistency models), compaction (space), concurrency (threads vs async).

---

## Single-Node KV Store

```
In-memory (like Redis):
  
  Data structure: hash table
    Key → Value mapping
    Time complexity: O(1) lookup (average case)
  
  Storage:
    ├─ All data in RAM
    ├─ Size: 1GB of data = 1GB of memory
    ├─ Cost: $1 per GB/month (AWS ElastiCache)
  
  Persistence:
    ├─ RDB: point-in-time snapshot (1GB)
    ├─ Frequency: 1x per hour
    ├─ Recovery: 1 hour of data loss
    │ (if you had 1 hour of writes)
    └─ Alternative: AOF (append-only file, slower)
  
  Throughput:
    ├─ Single-threaded: 100K QPS (one CPU core)
    ├─ Multi-threaded (new): ~500K QPS
    └─ Limited by: network (gigabit = ~100K small QPS)

Disk-based (like RocksDB, LevelDB):
  
  Storage:
    ├─ Uses SSD (fast, cheap)
    ├─ Size: 1TB of data = 1TB of disk
    ├─ Cost: $0.02 per GB (AWS EBS)
  
  Latency:
    ├─ Hot data (in cache): <1ms
    ├─ Cold data (on disk): 1-100ms
    └─ Write amplification: 10-100x (SSD writes)
  
  Throughput:
    ├─ Random reads: 10K QPS
    ├─ Sequential writes: 100K QPS
    └─ Limited by: SSD IOPS (4K QPS per SSD, need 25 SSDs for 100K)
```

---

## Partitioning (Sharding)

```
Single node problem:
  ├─ Can't scale: 1TB data → 1 node
  ├─ Can't load balance: all reads/writes to same node
  └─ Can't tolerate failure: 1 node down = service down

Solution: Partition data across N nodes

Range-based partitioning:
  
  Key range: 0-9999999 (user IDs)
  
  Partition 1: user_id 0-999999 → node1
  Partition 2: user_id 1000000-1999999 → node2
  Partition 3: user_id 2000000-9999999 → node3

  Lookup:
    user_id = 123456
    partition = 123456 / 1000000 = 0
    Go to: node1
  
  Pros:
    ✓ Simple (arithmetic)
    ✓ Range queries efficient (contiguous keys)
    ✓ Skew-aware (can adjust boundaries)
  
  Cons:
    ✗ Uneven load (hot users in one partition)
    ✗ Rebalancing hard (boundaries change)

Hash-based partitioning:
  
  Partition = hash(key) % N

  Example:
    key = "user_123"
    hash = sha256("user_123") = 0xabc123...
    partition = 0xabc123 % 3 = 1
    Go to: node2
  
  Pros:
    ✓ Even distribution (hash randomizes)
    ✓ Simple (modulo)
    ✓ Collision-resistant
  
  Cons:
    ✗ Range queries inefficient (keys scattered)
    ✗ Rebalancing expensive (adding node N→N+1)

Consistent Hashing (for rebalancing):
  
  Ring of hash values: 0 to 2^32
  
  Nodes placed on ring:
    Node A: position 100
    Node B: position 200
    Node C: position 300
  
  Key hashed to position:
    key "user_123" → hash = 150
    Go to: next node clockwise = Node B (200)
  
  Add Node D at position 250:
    ├─ Keys 200-250 move from B → D
    ├─ Keys 250-300 move from C → D
    └─ Only ~1/N keys rebalance
  
  Used by: Cassandra, DynamoDB, Redis Cluster
```

---

## Replication & Consistency

### Replication Factor

```
Each key stored on: R nodes (replication factor)

Example: R=3
  key "user_123"
  Replicas:
    - Node A (primary)
    - Node B (replica 1)
    - Node C (replica 2)

Write:
  Write to all 3 nodes
  Wait for: W nodes to ACK (write quorum)
  
  W=1: acknowledge after 1 write (fast, risky)
  W=3: acknowledge after all 3 writes (slow, safe)
  W=2: acknowledge after 2 of 3 (balanced)

Read:
  Read from: R nodes (read quorum)
  Return: most recent version (by timestamp/version number)
  
  R=1: read from 1 node (fast, may be stale)
  R=3: read from all 3 nodes (slow, consistent)
  R=2: read from 2 nodes (balanced)

Consistency guarantee:
  If W + R > replication_factor:
    ├─ Write goes to W=2, read goes to R=2
    ├─ 2+2 > 3 → overlap guaranteed
    └─ Always read latest write
  
  If W + R <= replication_factor:
    ├─ Write goes to W=1, read goes to R=1
    ├─ 1+1 <= 3 → no overlap
    └─ May read stale data
```

### Eventual Consistency (Cassandra-style)

```
Write:
  1. Sync write to W nodes
  2. Return ACK (even if other nodes not updated)
  3. Async write to remaining nodes

Replication lag:
  ├─ Node A updated: immediately
  ├─ Node B updated: 10-100ms later
  ├─ Node C: maybe never (if node down)

Read:
  1. Read from one node
  2. Return immediately (may be stale)

Repair:
  ├─ Background anti-entropy (compare replicas, fix mismatches)
  ├─ Merkle trees (efficient comparison)
  └─ Consistency achieved: eventually (hours)

Trade-off:
  ✓ Low latency writes (1 of 3 nodes ACKs)
  ✗ Eventual consistency (may read stale)
```

### Strong Consistency (Raft-style)

```
Raft consensus:
  
  Leader: one node designated leader
  Followers: N-1 nodes follow leader
  
  Write:
    1. Client → Leader
    2. Leader: append to log
    3. Leader → Followers (send log entries)
    4. Followers: reply ACK
    5. Leader: wait for quorum (N/2 + 1)
    6. Leader: commit + apply to state machine
    7. Leader → Client: ACK write
  
  Read:
    1. Read from leader only
    2. Guaranteed: latest data
    3. Latency: 2 RTTs (write) + 1 RTT (read) = slow

Trade-off:
  ✓ Strong consistency
  ✗ High write latency (quorum + commit)
  ✗ Unavailable if leader down (elect new)
```

---

## Compaction (Space Reclamation)

### Write Amplification Problem

```
Scenario: 1MB write → eventually 10MB written to SSD

Cause: LSM tree (log-structured merge tree)

  Level 0: 1MB (in memory, then flush)
  Level 1: 10MB (accumulate)
  Level 2: 100MB (accumulate)
  Level 3: 1GB (compact)

Each compaction:
  ├─ Read old + new data
  ├─ Merge
  ├─ Write merged result
  └─ Multiple rewrites per byte
  
  Example: 1MB write → 1MB L0 → 10MB L1 → 100MB L2 → 1GB L3
           1 * 1 + 10 * 1 + 100 * 1 + 1000 * 1 = 1111x writes
           (oversimplified, but illustrates problem)

Mitigation:
  ├─ Compression (gzip, snappy, zstd)
  ├─ Bloom filters (skip non-matching files)
  ├─ Tiering (faster leveling strategy)
  └─ Trade-off: CPU vs space
```

---

## Scale Calculation

```
1TB distributed KV store
1M QPS
R = 3 replicas
N = 10 nodes (1TB / 3 / 10 = 33 GB per node)

Storage:
  1TB * 3 = 3TB total (with replication)
  3TB / 10 nodes = 300 GB per node
  Cost: 10 nodes * $0.50/hour = $5/hour
  
Throughput:
  1M QPS / 10 nodes = 100K QPS per node
  
  Per-node throughput:
    ├─ Single-threaded: 100K QPS (achievable)
    ├─ Network: 100K * 100 bytes avg = 10 Gbps
    ├─ Single NIC: 1 Gbps (insufficient)
    └─ Need: 10 NICs per node (expensive)
  
  Alternative: smaller value size (10 bytes)
    ├─ 100K * 10 bytes = 1 Gbps (1 NIC sufficient)
    └─ More realistic

Latency (P99):
  ├─ Network: 1ms
  ├─ Disk I/O (cache miss): 10ms
  ├─ Serialization: 1ms
  └─ Total: ~12ms P99
  
  To achieve <5ms:
    ├─ Cache hit ratio >99%
    ├─ RAM size: 1TB * 0.01 / 3 = 3GB per node (fits)
    └─ Memory constraint: 10 * 3GB = 30GB (reasonable)
```

---

## Failure Modes

```
Node crash (out of disk, OOM):
  ├─ Detection: heartbeat timeout (3 sec)
  ├─ Re-replication: redistribute R=3 → 2 nodes
  ├─ Read: may fail if <R replicas
  └─ Write: fails immediately
  
  Recovery:
    ├─ Replace faulty node with new one
    ├─ Backfill data from other replicas
    ├─ Time: proportional to 1TB / bandwidth
    │  (100 Mbps → 80,000 seconds = 22 hours)
    └─ During backfill: service degraded

Partition (network split):
  ├─ Scenario: Node A-B partitioned from C
  ├─ A-B see: C down (will re-replicate to new node)
  ├─ C sees: A-B down (will re-replicate to new node)
  ├─ Result: 2 copies of same data (split brain)
  
  Resolution (eventual consistency):
    ├─ Quorum read: read from multiple nodes
    ├─ If conflict: use timestamp or version
    ├─ Choose: newer version (may lose writes)
    └─ Risk: data loss accepted (eventual consistency trade-off)

Hot partition (uneven load):
  ├─ Users: unevenly distributed (Zipfian)
  ├─ Result: partition 1 (hot users) overloaded
  ├─ Latency: P99 > 100ms
  ├─ Solution: sub-sharding (split hot partition)
  └─ Cost: rebalancing, complexity
```

---

## Code Example (Simple In-Memory KV Store)

```python
import hashlib
from threading import Lock, Thread
from collections import defaultdict
import time

class SimpleKVStore:
    def __init__(self, num_partitions=16):
        self.num_partitions = num_partitions
        self.partitions = [defaultdict(dict) for _ in range(num_partitions)]
        self.locks = [Lock() for _ in range(num_partitions)]
    
    def _partition_for_key(self, key):
        """Determine partition for key using hash."""
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return hash_val % self.num_partitions
    
    def get(self, key):
        """Fetch value for key."""
        partition_id = self._partition_for_key(key)
        with self.locks[partition_id]:
            partition = self.partitions[partition_id]
            if key in partition:
                return partition[key].get('value')
        return None
    
    def set(self, key, value, ttl=None):
        """Set key to value with optional TTL."""
        partition_id = self._partition_for_key(key)
        with self.locks[partition_id]:
            partition = self.partitions[partition_id]
            partition[key] = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl
            }
    
    def delete(self, key):
        """Delete key."""
        partition_id = self._partition_for_key(key)
        with self.locks[partition_id]:
            partition = self.partitions[partition_id]
            if key in partition:
                del partition[key]
    
    def evict_expired(self):
        """Background: remove expired keys."""
        while True:
            time.sleep(60)
            for partition_id in range(self.num_partitions):
                with self.locks[partition_id]:
                    partition = self.partitions[partition_id]
                    expired = [
                        k for k, v in partition.items()
                        if v['ttl'] and time.time() - v['timestamp'] > v['ttl']
                    ]
                    for k in expired:
                        del partition[k]

# Replication example
class ReplicatedKVStore:
    def __init__(self, nodes, replication_factor=3):
        self.nodes = nodes
        self.replication_factor = replication_factor
    
    def set(self, key, value, write_quorum=2):
        """Write to multiple nodes."""
        target_nodes = self._get_replicas(key)
        
        acks = 0
        for node in target_nodes[:self.replication_factor]:
            try:
                node.set(key, value)
                acks += 1
            except Exception:
                pass
        
        if acks >= write_quorum:
            return True
        else:
            raise Exception(f"Write failed: only {acks} ACKs (needed {write_quorum})")
    
    def get(self, key, read_quorum=2):
        """Read from multiple nodes, return latest."""
        target_nodes = self._get_replicas(key)
        
        values = []
        for node in target_nodes[:self.replication_factor]:
            try:
                val = node.get(key)
                if val:
                    values.append((val, node))
            except Exception:
                pass
        
        if len(values) >= read_quorum:
            # Return most recent
            return values[0][0]
        else:
            raise Exception(f"Read failed: only {len(values)} responses (needed {read_quorum})")
    
    def _get_replicas(self, key):
        """Get N replica nodes for key."""
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        start_idx = hash_val % len(self.nodes)
        return [self.nodes[(start_idx + i) % len(self.nodes)] 
                for i in range(self.replication_factor)]
```

---

## Interview Checklist

- [ ] Partitioning: hash vs range tradeoffs
- [ ] Consistent hashing for rebalancing
- [ ] Replication factor and quorum (W + R > RF)
- [ ] Eventual vs strong consistency models
- [ ] Write amplification and compaction
- [ ] Failure modes: node crash, partition, hot keys
- [ ] Scale: 1TB data, 1M QPS, <10ms latency
- [ ] LSM trees vs B-trees

## Common Wrong Answers

- ❌ "Single node" — doesn't scale to 1M QPS
- ❌ "Replicate everything to all nodes" — network bottleneck, writes expensive
- ❌ "No consistency model" — can't reason about conflicts
- ❌ "Always strong consistency" — write latency too high
- ❌ "No compaction" — disk fills up, write amplification ruins performance
- ❌ "Ignore hot keys" — load imbalance kills latency
