# Reproduce and Minimize: From Flaky to Deterministic

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Flaky Bugs Are Harder Than Deterministic Bugs

A bug that reproduces 100% of the time: Easy to debug.
A bug that reproduces 5% of the time: Can take 10x longer.

**The trap:** You can't fix what you can't reproduce.

**The solution:** Capture the minimal reproducer — the smallest input that triggers the bug.

## Capturing the Bug: Seeds, Inputs, and Environment

When a bug occurs, capture:

1. **Seed/RNG state** (if randomness involved)
   - Test framework seeds: `--seed=42`
   - Random data generators: capture the seed used
   - Allows: `pytest --seed=12345 tests/flaky.py` (deterministic replay)

2. **Input data** (the exact data that triggered it)
   - Logging: "Processing order ID 123456789"
   - Capturing: Save the input to a file (JSON, protobuf, etc.)
   - Replay: Load from file, run test with that input

3. **Environment variables** (config that might matter)
   - Timezone: TZ, system clock skew
   - Heap size: `-Xmx`
   - Number of threads: Thread pool size
   - Logging level: DEBUG vs INFO

4. **System state** (conditions at time of failure)
   - Load average (system busy?)
   - Memory available
   - Disk I/O patterns

```
Example: Flaky multi-threaded test
  
Failure captured:
  Seed: 42
  Num threads: 16 (on this machine)
  Heap: 512MB
  Input: 1000 order objects (list.json)
  
Minimal reproducer:
  python -Xfrozen_modules=off test_orders.py \
    --seed=42 \
    --threads=16 \
    --heap=512MB \
    --input=list.json
```

## Delta Debugging: Shrinking the Input

You captured the bug with 10,000 input items. Can you shrink it to 100? To 10?

**Delta debugging:** Binary search to find the smallest subset that triggers the bug.

```
Failing input: [item_1, item_2, ..., item_10000]
Success: Find minimal subset [item_5, item_999, item_8234]

Process:
  1. Remove half: [item_1, ..., item_5000]
     - Does it still fail? Keep half removed
     - Doesn't fail? Put half back, try other half
     
  2. Repeat until you have minimal set
     
Result: 10,000 items → 3 items that trigger bug
```

**Why:**
- Smaller input = easier to understand
- 10,000 items: 10 hours to analyze
- 3 items: 5 minutes to understand the pattern

## Deterministic Replay: The Goal

Once you have a reproducer, it should be deterministic:

```
Bad reproducer:
  "Run the system for a few hours, it might crash"
  
Good reproducer:
  "Run: python test_race_condition.py --seed=12345"
  Result: Fails 100% of the time in < 1 sec
```

## Real Example: Flaky Pagination Bug

**Initial report:** "Users sometimes can't see last page of results."

**Initial symptoms:**
- Happens 2% of the time
- No clear pattern
- Flaky on CI, works locally

**Capturing the bug:**

```
Add logging to understand when it happens:

  @app.get("/items", page: int, size: int)
  def get_items():
    total = db.count()  # 1000 items
    start = (page - 1) * size
    
    # Log for debugging
    print(f"page={page}, size={size}, total={total}, start={start}")
    
    items = db.query().offset(start).limit(size).fetch()
    
    if not items and page > 1:
      # This is the bug! Last page is empty
      print(f"BUG: Requested page {page} but got no items")
    
    return items

Run tests, capture all cases where "BUG" logged:
  page=3, size=10, total=25, start=20  ← This triggers it!
  
Data: Exactly 25 items, requested page 3 (items 20-29)
      But only items 0-24 exist → page 3 is empty
```

**Root cause identified:** Off-by-one in pagination calculation.

**The fix:**

```python
# Old (wrong):
items = db.query().offset(page * size).limit(size)

# New (correct):
items = db.query().offset((page - 1) * size).limit(size)
```

**Regression test (captures the minimal case):**

```python
def test_last_page_pagination():
    # Minimal input: 25 items, ask for page 3 of 10-item pages
    db.insert([Item(i) for i in range(25)])
    
    page3 = get_items(page=3, size=10)
    
    # Bug: Empty list
    # Fixed: [Item(20), Item(21), ..., Item(24)]
    assert len(page3) == 5
    assert page3[0].id == 20
```

## Environment Sensitivity: Why It Fails on CI but Not Locally

Same bug, different environments → different thread schedules, timings, etc.

```
Symptom: Test fails on CI (Ubuntu 20.04, Python 3.10, threads=8)
         Passes on dev machine (macOS, Python 3.12, threads=16)

Hypothesis: Race condition or timing sensitive

Solution: Replicate CI environment locally
  docker run -it ubuntu:20.04
  apt-get install python3.10
  pytest --seed=<same_seed_from_ci>

Or: Use CI machine's environment variables in test
  export TZ=UTC
  export PYTHONHASHSEED=0
  python -u test_race.py
```

## Interview: Capturing and Debugging

**Q: "We have a flaky test that fails 1% of the time. How would you fix it?"**

Weak answer:
```
"Add more logging? Run it more times?
Or maybe use locks to make it deterministic?"
(No systematic approach)
```

Strong answer:
```
"1. Capture the failure:
   - When it fails on CI, save the test seed/environment
   - Reproduce locally with same seed: pytest --seed=ABC
   - If reproducible: Delta debug to minimal input
   
2. Once deterministic, debug:
   - TSAN for race conditions
   - Print timing/ordering
   - Run under debugger with breakpoints
   
3. Fix based on evidence (not guess):
   - If race: Use lock or atomic
   - If timing: Use explicit sync (semaphore)
   - If data: Fix algorithm
   
4. Verify fix:
   - Run with same seed: Should pass 100%
   - Run 1000x with random seeds: Should never fail
   - Add regression test with minimal input
"
```

## Checklist

- [ ] Seed/RNG captured (can replay with `--seed=X`)
- [ ] Input data saved (JSON file, query ID, etc.)
- [ ] Environment captured (timezone, heap size, thread count)
- [ ] Minimal reproducer identified (delta debugged)
- [ ] Deterministic replay verified (fails 100% of time with seed)
- [ ] Regression test written (captures minimal case)
- [ ] CI environment replicated locally (for CI-only failures)

## Common Mistakes

1. **Not capturing the seed.** Next day: "Couldn't reproduce with --seed=0. Which seed was it?"
2. **Input too large.** "Reproducer uses full production database dump (50GB)." Can't debug efficiently.
3. **Environment not captured.** Works on dev, fails on CI, but CI environment never documented.
4. **Not making it deterministic before fixing.** Fix a race condition but test is still flaky → did you actually fix it?
5. **No regression test.** Bug fixed, but test doesn't capture it, and bug reappears in next release.

