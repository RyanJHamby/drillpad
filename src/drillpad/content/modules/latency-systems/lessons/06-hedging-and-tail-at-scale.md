# Hedging & Tail-at-Scale

## Tail Latency Problem

```
P99 = 100ms (1% of requests take >100ms)
Problem: 1% * 1M QPS = 10K slow requests

User experience:
  ├─ 99% instant (good!)
  ├─ 1% slow (bad! user feels lag)
  └─ Compound: web page + 10 requests = 1-(0.99^10) = 9.5% page slow
```

## Hedged Requests

```
Naive (wait for one server):
  ├─ Send request to Server A
  ├─ Wait for response
  ├─ P99 latency: 100ms
  └─ Result: slow 1% of time

Hedging (backup request):
  ├─ Send request to Server A
  ├─ Wait 50ms
  ├─ If no response by 50ms: also send to Server B (backup)
  ├─ Return: first response from either (whichever is faster)
  ├─ P99 latency: ≈ min(wait_time, A_latency, B_latency)
  │  └─ Very likely one of two is fast
  └─ Result: P99 ≈ 50ms (2x better!)

Cost:
  ├─ Extra QPS: 1% * 1M = 10K extra requests
  ├─ Server load: +1% (negligible)
  ├─ Network: +1% (negligible)
  └─ Benefit: P99 latency 2x better
```

## Adaptive Hedging

```
Dynamic hedge delay based on latency:

Scenario: Server is overloaded
  ├─ Baseline P50: 10ms
  ├─ Current P50: 30ms (3x slower)
  ├─ Inference: system overloaded
  ├─ Reduce hedge delay: 50ms → 20ms
  ├─ Hedge sooner: more backups

Implementation:
  ├─ Track: p_latency in sliding window (last 1 sec)
  ├─ Hedge delay = base_delay * (current_p50 / baseline_p50)
  └─ Result: stay adaptive
```

## Implementation Cost

```
Request lifecycle:
  ├─ Send primary: 0.1ms
  ├─ Wait for hedge timer: 50ms (timer cost ~0)
  ├─ Send backup (if timeout): 0.1ms
  ├─ Receive & pick faster response: <1ms
  
Net overhead:
  ├─ CPU: negligible (async, no spinning)
  ├─ Network: 1% extra QPS
  └─ Memory: request context (small)

Benefit:
  ├─ P50: unchanged (~10ms)
  ├─ P99: ~50ms (not 100ms)
  ├─ User-facing: noticeably snappier
```

---

## Interview Checklist

- [ ] Tail latency: 1% slow request affects compound queries
- [ ] Hedging: send backup after timeout
- [ ] Cost: 1% extra QPS, negligible CPU
- [ ] Benefit: P99 latency 2x-4x better
- [ ] Adaptive: adjust hedge delay based on load

## Common Wrong Answers

- ❌ "Send two requests always" — wastes resources
- ❌ "No hedging" — P99 high, user experience suffers
- ❌ "Hedge immediately" — too many backups, wasted QPS
