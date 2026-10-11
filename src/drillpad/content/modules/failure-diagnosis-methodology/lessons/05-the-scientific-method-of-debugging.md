# The Scientific Method of Debugging: Hypothesis Elimination Under Uncertainty

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Guessing vs. Reasoning

Most engineers debug by guessing: "Maybe it's network? Let me add logging... maybe it's the database? Let me restart it... maybe it's a race condition?"

**The trap:** You spend 2 hours guessing and patch the wrong thing.

**The alternative:** Treat debugging as hypothesis elimination. Each test eliminates possibilities. The goal: maximize information per unit of work.

## The Scientific Method of Debugging

```
Step 1: Observe
  Gather facts (not theories)
  - What changed? (code? traffic? deployment?)
  - When did it start? (timestamp)
  - Who is affected? (one user? all? geographic pattern?)
  - What's the error? (exception, hang, corruption, wrong output?)
  
Step 2: Hypothesize (2-3 candidates)
  - Hypothesis A: Lock contention (threads waiting)
  - Hypothesis B: Memory leak (heap growing)
  - Hypothesis C: Network partition (upstream slow)
  
Step 3: Predict
  - "If it's A: CPU will be low, threads will be BLOCKED"
  - "If it's B: Heap histogram will show large object growth"
  - "If it's C: Ping to upstream will be high"
  
Step 4: Test (choose one observation that discriminates)
  - Run: async-profiler (discriminates A vs B vs C)
  - One test eliminates multiple hypotheses
  
Step 5: Iterate
  - Evidence kills hypothesis A → focus on B and C
  - New test narrows further
```

## The Debug Log: Your Evidence Trail

Keep a debug log. Write down:
1. Hypothesis (what you think it is)
2. Test (what you'll check)
3. Result (what the evidence shows)
4. Conclusion (what you've eliminated)

```
Debug log for "P99 latency spiked 50ms → 500ms, no code change"

Hypothesis 1: GC pause
  Test: Check GC logs (grep 'Full GC' last 5 min)
  Result: No Full GC in logs. Minor GC every 100ms (normal)
  Conclusion: ELIMINATED

Hypothesis 2: Lock contention
  Test: Run async-profiler, check for BLOCKED threads
  Result: 80% of threads BLOCKED on ReentrantLock (lock_instance_42)
  Conclusion: CONFIRMED

Next test: Which code holds lock_instance_42?
  Test: Grep codebase for "lock_instance_42" or locks held during...
  Result: Shared HashMap in cache manager, held during resize
  Conclusion: Root cause found
```

**Why this matters:**
- You have an evidence trail to show (not "I think it's X")
- If you're wrong, you can backtrack (logged what failed)
- Easier to escalate (evidence to show leadership)
- Interview signal: Shows systematic thinking

## Information Per Test: The Efficiency Metric

Not all tests are equal. Some tests discriminate between many hypotheses; others check one thing.

```
Low-efficiency tests:
  - "Add logging to see if code path executes"
    Tells you: One thing (did code run?)
    Cost: 5 min redeploy
    Information per time: Low
    
High-efficiency tests:
  - "Run async-profiler for 10 sec"
    Tells you: Which functions, thread states, locks, CPU usage
    Cost: 10 sec
    Information per time: High
```

**Choose tests by information content, not by ease.**

## When to Stop: Stopping Rules

Know when to escalate. Don't spend 2 hours debugging if the root cause is likely outside your system.

```
Stop and escalate if:
  1. Test is not discriminating (5+ tests, no new info)
     → Escalate to teammate with more context
     
  2. You've confirmed root cause but can't fix it
     → "Lock held by library code" → escalate to library owner
     
  3. Evidence points outside your system
     → "Network packet loss from ISP" → escalate to network team
     
  4. Reproducer is flaky (happens 1% of time)
     → Can't make progress with unreliable test
     → Document hypothesis, escalate for monitoring
     
  5. Time spent > benefit of fix
     → P99 latency spike at 3am, temporary issue
     → Fix the immediate problem (restart), investigate later
```

## Worked Example: 3-Hour Debugging Session

**Symptom:** Production job fails every 2 days with OOM after 18 hours of running.

**Session start (0:00):**

Hypothesis 1: Memory leak (objects retained)
  Test: Java heap dump (1 GB, takes 10 min to collect)
  Result: Object histogram shows ByteBuffer.allocate() 50% of heap
  → Confirms allocation spike, but which code?

Hypothesis 2: Unbounded cache (cache not evicting)
  Test: Grep code for "cache.put()" without TTL
  Result: Found line: `cache.put(key, value)` in DataProcessor.process()
  → Likely culprit

Hypothesis 3: Configuration issue (cache size too large)
  Test: Check config: cache size = unlimited
  Result: CONFIRMED (should be 256MB max)
  
**Diagnosis:** Unbounded cache + high data velocity = heap fills in 18 hours

**Fix candidates:**
  A. Set cache.maxSize = 256MB (1 min change, 1 sec deploy)
  B. Add eviction policy TTL (5 min change, 1 sec deploy)
  C. Use external cache (Redis) (2 hour change)
  
**Decision:** Apply A (quick win), then B (permanent fix)

**Result:** Job now runs indefinitely with max 256MB cache

**What made this efficient (vs. inefficient):**

Efficient:
- Started with symptom (OOM every 2 days)
- One test (heap dump) narrowed hypothesis
- Found root cause (unbounded cache)
- Applied proportional fix (config change)

Inefficient (alternative path):
- "Maybe it's GC" → run GC tuning (wasted 1 hour)
- "Maybe it's thread leak" → count threads (they're normal)
- "Maybe it's disk I/O" → profile disk (not the issue)
- → 3 hours wasted before finding real cause

## Interview: Demonstrating the Method

**Q: "Walk me through how you'd debug a flaky test that fails 2% of the time."**

Weak answer:
```
"Uh, I'd add logging? Or run it more times to see the pattern?
Maybe it's a race condition?"
(Scattered, no method, no decision tree)
```

Strong answer:
```
"Systematic approach:

1. Observe: Does it fail with same seed? Same test order?
   Test: Run with --seed=42 (deterministic)
   If fails same way: Not flaky, something's wrong with that seed
   If fails differently: True flakiness

2. Hypothesize: Race? Timing? External service?
   Test: Run with TSAN (Thread Sanitizer)
   If TSAN reports: Race confirmed
   If not: Timing or external

3. For timing:
   Test: Run with JitterTimeout (random delays)
   If fails: Timing dependent
   
4. For external service:
   Test: Mock external service (always return OK)
   If fails: Not external, internal logic
   
5. Debug log for evidence: [would show each test result]
   
Once we confirm the cause, the fix is straightforward."
```

Green flags:
- Method (not guessing)
- Decision tree (if X then test Y)
- One test per iteration
- Evidence trail (showing work)

## Checklist

- [ ] Debug log created (start one for any non-trivial issue)
- [ ] Hypothesis clearly stated (not vague)
- [ ] Test designed to discriminate (not just confirm one hypothesis)
- [ ] Result recorded (fact, not interpretation)
- [ ] Stopping rule defined (when to escalate)
- [ ] Evidence trail shows path (could explain to teammate)
- [ ] Root cause confirmed before fix

## Common Mistakes

1. **Changing two things at once.** "I'll restart the service AND increase heap." Now you don't know which fixed it.
2. **Testing the wrong hypothesis.** "I think it's network, so I check CPU." Doesn't discriminate.
3. **No debug log.** 2 hours later: "I think I checked GC logs but I'm not sure."
4. **Too many hypotheses.** 10 candidates means you won't narrow anything. Stick to 2-3.
5. **Not stopping.** Stuck for 3 hours → escalate. The root cause might be outside your expertise.

