# Load Balancing: Algorithms and Trade-Offs

## Why Load Balancing?

Single server can handle 10k QPS. You have 100k QPS.

```
Option 1: Single server (bad)
  - Overloaded, queues grow, latency spikes

Option 2: Multiple servers + load balancer
  - Distribute load evenly
  - Balance: fairness vs affinity vs complexity
```

## Round-Robin

Distribute requests in order: server 1, 2, 3, 1, 2, 3, ...

```
Request 1 → Server 1
Request 2 → Server 2
Request 3 → Server 3
Request 4 → Server 1 (cycle)
```

**Pros:** Simple, fair
**Cons:** Ignores server load (slow server gets same as fast)

## Least-Loaded (Least Connections)

Send request to server with fewest active connections.

```
Server 1: 10 active connections
Server 2: 50 active connections
Server 3: 5 active connections

New request → Server 3 (fewest)
```

**Pros:** Adapts to server load
**Cons:** Higher overhead (track connection count)

## Consistent Hashing

Hash the request, server = hash(request) % num_servers

```
hash(user_id=123) % 3 servers = Server 1
hash(user_id=456) % 3 servers = Server 2
hash(user_id=789) % 3 servers = Server 1

Same user always goes to same server (good for caching)
```

**Pros:** Sticky sessions, cache-friendly, minimal redistribution on server failure
**Cons:** May be unbalanced (some users > others)

## Real Trade-Off: Trading Order Distribution

```
Scenario: 3 order servers (matching engines), 100k orders/sec

Round-robin:
  Each server gets ~33k orders/sec
  Good: even distribution
  Bad: different order sequences on each server
  Problem: If server crashes, orders to it are lost

Sticky (consistent hash):
  User A → always Server 1
  User B → always Server 2
  Good: order sequence preserved, local caching
  Bad: if Server 1 slow, User A bottlenecked

Least-loaded:
  Server 1: handling 40k orders/sec (slow)
  Server 2: 35k (normal)
  New order → Server 2
  Good: balances based on actual load
  Bad: order sequence per user changes (breaks local caching)
```

## Real Example: AWS ALB

```
ALB routes traffic:
  - Round-robin for stateless services (web API)
  - Sticky for stateful (sessions, cache)
  - Least-outstanding for uneven response times
```
