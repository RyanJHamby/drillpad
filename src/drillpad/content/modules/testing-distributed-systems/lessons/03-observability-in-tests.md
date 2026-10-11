# Observability in Tests: Debugging Test Failures

## Overview

When a distributed test fails, how do you know what went wrong? This lesson covers:
1. Structured logging in tests
2. Timeline reconstruction (what happened when?)
3. Causality tracking (which event caused which?)
4. Debugging distributed test failures

---

## Structured Logging

Instead of random print statements, log with context:

```rust
// Bad: Hard to parse, hard to correlate
println!("Server A sent message");
println!("Server B received");

// Good: Structured, parseable
log!(
    "event=send server=A message_id=123 dst=B time=1000ms"
);
log!(
    "event=receive server=B message_id=123 src=A time=1005ms"
);
```

**Benefits:**
- Easy to filter (grep for `server=A`)
- Easy to reconstruct timeline (sort by time)
- Easy to correlate (match message_id)

---

## Timeline Reconstruction

Collect all logs, sort by timestamp, replay:

```
time=1000ms  event=send   server=A dst=B msg=write
time=1001ms  event=crash  server=B reason=oom
time=1002ms  event=send   server=A dst=B msg=write (retry)
time=1003ms  event=recover server=B state=empty
time=1004ms  event=receive server=B src=A msg=write
```

Immediately visible:
- B crashed at 1001ms (lost in-memory state)
- A retried at 1002ms (good)
- B recovered but lost B's own writes

---

## Causality Tracking

Use vector clocks to track causality:

```
Message 1: [server_a=1, server_b=0]  (A sends first)
Message 2: [server_a=1, server_b=1]  (B received message 1, sends)
Message 3: [server_a=2, server_b=1]  (A received message 2, sends)

Causality: Message 1 → Message 2 → Message 3
```

Why? If test fails, you know the exact order of events.

---

## Example: Failed Test Debug

Test fails: "Timeout waiting for server B to acknowledge"

Logs show:
```
time=100ms  event=send   server=A dst=B msg=prepare
time=101ms  event=receive server=B src=A msg=prepare
time=102ms  event=process server=B msg=prepare (takes 10ms)
time=112ms  event=send   server=B dst=A msg=ack
time=150ms  event=timeout server=A reason=no_ack_received

ANALYSIS:
  - B received message (good)
  - B processed message (good)
  - B sent ACK at 112ms (good)
  - A still waiting at 150ms (bad)
  - Gap: 112ms → 150ms, no logs
  - Hypothesis: A crashed before receiving ACK?
```

---

## Distributed Tracing in Tests

Add trace IDs to follow messages end-to-end:

```rust
log!(trace_id=123, "send msg from A to B");
log!(trace_id=123, "B receives msg");
log!(trace_id=123, "B processes msg");
log!(trace_id=123, "B sends response");
```

Later, reconstruct trace 123:
```
Grep for trace_id=123:
  A: send @ 1000ms
  B: receive @ 1005ms
  B: process @ 1006ms (took 5ms)
  B: respond @ 1007ms
  A: receive @ 1012ms
  
Total latency: 12ms (1000→1012)
  Network: 5ms in, 5ms out
  Processing: 1ms
```

---

## Real Example: Consensus Test Failure

Test: "3 servers reach consensus on value X"

Failure: Server C doesn't see value X

Debug logs:
```
A: log_entry[term=1, index=1] = "X"
B: log_entry[term=1, index=1] = "X"
C: log_entry[term=1, index=0] (never gets index 1!)

Timeline:
  1000ms: A appends X, sends to B
  1001ms: B receives, appends X
  1005ms: A sends to C (replication)
  1006ms: C crashes (OOM)
  1007ms: A sends to C again (C doesn't respond)
  
Conclusion: C crashed during replication.
Recovery path: Does C replay logs from stable storage?
```

---

## Key Takeaways

1. **Structured logging** = parseable, filterable
2. **Timeline reconstruction** = understand what happened when
3. **Trace IDs** = follow messages end-to-end
4. **Vector clocks** = prove causality
5. **Logs are your debugger** = print wisely

---

## Q&A

**Q: How much logging is too much?**

Log every major event (send, receive, process, crash).
Don't log inside tight loops (too noisy).

**Q: Should I log to file or memory?**

Memory (fast), but limit size (1000 events). On failure, dump to file.

**Q: How do I correlate events across servers?**

Synchronized clocks (in simulation) or vector clocks (in practice).
