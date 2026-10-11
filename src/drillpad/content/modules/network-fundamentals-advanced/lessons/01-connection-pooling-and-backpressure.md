# Connection Pooling & Backpressure - Managing Scarce Resources

## Why Connection Pools Exist

Opening a TCP connection is expensive:

```
TCP 3-way handshake:
  Client: SYN
  Server: SYN-ACK
  Client: ACK
  
  Each roundtrip: ~1ms (on same network)
  Total: 3ms per connection
  
  Plus TLS (if HTTPS):
  - TLS handshake: another 2-3ms
  - Total: 5-6ms per connection
  
Reusing a connection:
  Open once: 5ms
  100 requests reusing it: 5ms total
  100 new connections: 500ms total
  
Difference: 100x slowdown!
```

Connection pools cache open connections, reuse them.

## Connection Pool Sizing

```
Rule of thumb:
  pool_size = num_workers * avg_concurrent_requests_per_worker

Example: Web server with 8 workers, each might handle 10 concurrent requests
  pool_size = 8 * 10 = 80 connections

Too small (pool_size = 10):
  - Requests wait for available connection
  - Latency increases
  - Throughput decreases

Too large (pool_size = 1000):
  - Wastes memory
  - Database struggles (more connections = more overhead)
  - Both sides need capacity

Database side:
  PostgreSQL default: max_connections = 100
  If 10 web servers with 80 connections each = 800 connections needed
  
  Increase PostgreSQL: max_connections = 1000
  Or: Use connection pooler (PgBouncer) to multiplex
```

## Detecting Connection Pool Exhaustion

Your pool has 80 connections, all in use.

Request 81 comes in. Now what?

```
Bad behavior (no backpressure):
  Request 81: Try to get connection
  Pool: None available
  Request 81: Create new connection (violates pool size)
  → Now 81 connections open → database overloaded

Good behavior (with backpressure):
  Request 81: Try to get connection
  Pool: None available
  Request 81: Wait (block) until one is released
  Request 1: Completes, connection returned to pool
  Request 81: Gets connection, proceeds
  → Pool size stays at 80
```

## Backpressure: The Key Concept

**Backpressure = Stop accepting work when you can't handle it.**

```
Queue filling up:
  Producers (API requests) → Queue → Consumers (workers)
  
Without backpressure:
  Producers keep adding to queue (grows unbounded)
  Queue = 10K pending requests
  Consumers are slow (overloaded)
  Memory exhausted
  System crashes
  
With backpressure:
  Queue max size = 100
  Queue full? Producer waits/rejects new request
  Consumer processes, queue shrinks
  Producer continues when space available
  → System stays stable under load
```

## Real Backpressure Example: HTTP 503

```
Server gets swamped:
  - Connection pool exhausted
  - Message queue full
  - CPU overloaded
  
Response to client:
  HTTP 503 Service Unavailable
  
This is backpressure: "I can't handle more right now, try again later."
```

## Connection Pool Monitoring

```
Alert if:
  - Active connections > 80% of max
    (only 20% headroom left)
  - Wait time > 100ms
    (requests waiting for connection)
  - Failed connections > 1%
    (pool hitting limits)
```

## Interview Pattern: Pool Exhaustion

```
Q: "Your API starts timing out (5s instead of 100ms).
   Database says connections are fine. What's wrong?"

Weak answer:
  "Database is slow"
  (❌ Doesn't match facts)

Strong answer:
  "Sounds like connection pool exhaustion:
  
  1. Diagnosis:
     - Latency went from 100ms to 5s
     - Database says connections OK (not max_connections hit)
     → Problem is on client side (API's pool)
  
  2. Check pool metrics:
     - Active connections: 80/80 (full!)
     - Wait time: 5s (requests waiting for connection)
     - Queue length: 1000 pending
     
  3. Root cause:
     - Each request takes longer (database slow)
     - Requests hold connections longer
     - Pool empties slower
     - New requests pile up, wait for connection
     - Added 5s wait time to each request
  
  4. Why doesn't database see it?
     - Database max_connections = 200
     - API pool = 80
     - API is bottleneck, not database
  
  5. Fixes (in order):
     a) Short term: Increase pool size (80 → 120)
        Cost: Faster requests (release connections sooner)
        Trade: More database connections
     
     b) Long term: Reduce per-request latency
        Why: Connections released faster
        Fix: Optimize database queries
     
     c) Monitor: Set alert pool_active > 70%
        Catch overload before timeouts
  
  6. Validation:
     - Increase pool: Latency drop to 500ms (wait time reduced)
     - Optimize query: Latency drop to 100ms (actual fix)"

Why this signals good judgment:
  - You diagnosed client-side vs server-side
  - You understood why metrics didn't match
  - You had short-term (increase pool) and long-term (optimize) fixes
  - You'd monitor to prevent next time
```

## Checklist: Connection Pool Health

- [ ] Monitor active connections (alert at 80%)
- [ ] Monitor wait time (alert if > 100ms)
- [ ] Test pool under load (capacity planning)
- [ ] Validate pool size matches expected concurrency
- [ ] Have recovery strategy (circuit breaker, queue limit)
- [ ] Log pool exhaustion events (find patterns)

## What This Signals

- You've scaled systems with resource limits
- You understand backpressure (not just "add capacity")
- You can diagnose exhaustion scenarios
- You think about cascading failures
