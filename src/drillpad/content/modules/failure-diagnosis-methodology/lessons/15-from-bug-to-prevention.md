# From Bug to Prevention: Root Cause, Regression Tests, and Guardrails

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Bugs Recur

You fix a bug on Monday. Same bug happens again on Friday.

**Why:**
- No regression test (bug was fixed but not captured)
- Root cause not addressed (fixed symptom, not underlying issue)
- No guardrail (no code to prevent this category of bug)

## Root Cause vs. Proximate Cause

```
Proximate cause: What immediately caused the bug?
  "Variable X was NULL"

Root cause: Why was variable X NULL?
  "We didn't validate input from user"

Short-term fix (proximate): Add NULL check
  if (x != null) { ... }

Long-term fix (root cause): Add input validation
  class Validator:
    def validate_input(input):
      if not input.x:
        raise ValueError("X is required")
```

**Example:**

```
Symptom: Payment failed for user with amount $0

Proximate cause: Code doesn't handle $0 amount
  if amount == 0:
    raise error  ← Fix here

Root cause: Form accepted $0 amount from user
  <input type="number" min="0.01" />  ← Fix here

Long-term: Add validation at every layer
  1. Frontend: input type="number" min="0.01"
  2. API: assert amount > 0
  3. Database: CONSTRAINT amount > 0
  4. Tests: test_zero_amount() raises error
```

## The Regression Test: Capture the Case

Once you fix a bug, write a test that would fail with the old code.

```python
# Bug: Pagination off-by-one

# Old code (broken):
def paginate(items, page, size):
    start = page * size  # ← Wrong! Should be (page - 1) * size
    return items[start:start+size]

# This test would fail with old code:
def test_pagination_page_3():
    items = list(range(100))  # [0, 1, ..., 99]
    
    # Page 3, size 10 should be items 20-29
    result = paginate(items, page=3, size=10)
    
    assert result == list(range(20, 30))
    # Old code returns items 30-39 (wrong!)
    # New code returns items 20-29 (correct!)

# New code (fixed):
def paginate(items, page, size):
    start = (page - 1) * size  # ← Fixed
    return items[start:start+size]

# Now test passes
```

**Key:** Test captures the exact case that was broken. If someone reverts your fix, test fails.

## Guardrails: Preventing the Category of Bug

Once you fix a bug, add code to prevent that category.

**Category 1: Off-by-one**

```python
# Add assertions to catch off-by-one errors
def paginate(items, page, size):
    assert page >= 1, "page must be >= 1"
    assert size >= 1, "size must be >= 1"
    
    start = (page - 1) * size
    end = start + size
    
    # Sanity check
    assert start >= 0, "start index must be >= 0"
    assert start < len(items), "page out of range"
    
    return items[start:end]
```

**Category 2: Null/None Handling**

```python
# Add type hints + static checking
def process_user(user: User) -> Result:  # user is required
    # Not optional, so mypy will catch None at call sites
    return Result(user.id)

# Calling with None will be caught by mypy:
process_user(None)  # ← Static type error

# Add runtime check for safety
def process_user(user: User) -> Result:
    if user is None:
        raise ValueError("user cannot be None")
    return Result(user.id)
```

**Category 3: Numeric Overflow/Underflow**

```python
# Old code (can overflow)
def add_balance(account, amount):
    new_balance = account.balance + amount  # No bounds check!
    account.balance = new_balance

# Guardrails (added)
def add_balance(account, amount):
    assert amount >= 0, "amount must be non-negative"
    assert amount <= MAX_TRANSACTION, f"amount exceeds max {MAX_TRANSACTION}"
    
    new_balance = account.balance + amount
    assert new_balance >= 0, "balance would go negative"
    assert new_balance <= MAX_BALANCE, "balance would exceed max"
    
    account.balance = new_balance
```

**Category 4: Type Errors**

```python
# Old code (type error not caught)
def is_even(n):
    return n % 2 == 0

is_even("hello")  # TypeError, but not caught at call time!

# Guardrails (add type hints + checking)
from typing import Union

def is_even(n: int) -> bool:
    if not isinstance(n, int):
        raise TypeError(f"Expected int, got {type(n)}")
    return n % 2 == 0

# mypy catches type errors:
is_even("hello")  # mypy error: Expected int, got str
```

## Telling the Story: The "Hardest Bug" Interview

Interview question: **"Tell me about the hardest bug you fixed."**

**Bad answer:**
```
"It was hard to debug. I fixed it. It took 2 hours."
(No story, no learning)
```

**Good answer (using STAR format with debugging narrative):**

```
"I was building a payment processor. Users reported failed transactions
on weekdays but not weekends.

Situation:
  - Payments occasionally failed (5% failure rate)
  - Only during business hours (9am-5pm)
  - Worked fine on weekends
  
Task:
  - Debug why this was happening
  - Fix it to prevent recurrence

Action:
  1. Initial hypothesis: It's a load issue (more traffic weekdays)
     Test: Compare load metrics weekday vs weekend
     Result: Similar load. Not load-related.
  
  2. New hypothesis: Something scheduled runs weekdays?
     Test: Check cron jobs, scheduled tasks
     Result: Batch job runs 9am-5pm on weekdays, blocks database
     
  3. Root cause found: Batch job held a lock during daytime
     It was processing historical data
     When payment request came in, it waited for batch to finish
     Timeout (5 sec) expired, payment failed
  
  4. Short-term fix: Increase timeout to 30 sec
     Result: Failures dropped from 5% to 0.5%
     
  5. Long-term fix: Batch job now uses READ UNCOMMITTED
     Doesn't block payments anymore
     
Result:
  - Failure rate: 5% → 0% (measured over 1 month)
  - Learned: Batch jobs can block user requests
  - Added guardrail: Every long-running job now has timeout check
  - Regression test: Mock slow database, ensure payment completes
  
What I'd do differently:
  - Add monitoring earlier (would have caught this in hours, not days)
  - Isolate batch and user databases (prevent lock blocking)
"
```

**Why this is strong:**
1. **Situation:** Clear problem statement
2. **Hypothesis trail:** Shows systematic debugging (not guessing)
3. **Root cause identified:** Not just symptom fixed
4. **Root cause addressed:** Batch job redesigned
5. **Measurement:** Failure rate improved, monitored
6. **Prevention:** Guardrails added (timeout check)
7. **Reflection:** What you'd do differently

## Incident Postmortem: Learning from Bugs

After a production incident (or serious bug), conduct a blameless postmortem:

```
1. Timeline: What happened, when?
   10:05am: Alert fires (P99 latency spike)
   10:07am: Oncall investigates
   10:15am: Root cause found (query without index)
   10:20am: Workaround applied (restart service)
   10:30am: Query fixed and re-deployed
   11:00am: Verified, all systems normal
   
2. Root cause: Why did it happen?
   - Developer optimized query for common case
   - Edge case (large dataset) not tested
   - No index on new field
   
3. Impact: How bad was it?
   - 15 minute outage
   - 500 requests failed
   - 50 users affected
   
4. Detection: How fast was it caught?
   - Alerting: 5 minutes to detection (slow)
   - Could have been faster with earlier alert threshold
   
5. Recovery: How was it fixed?
   - Short term: Restart service (bought time)
   - Long term: Add index (permanent fix)
   
6. Prevention: How do we prevent recurrence?
   - Load test with large datasets (catches performance regressions)
   - Add index on any field used in WHERE clause
   - Add monitoring alert for query latency
   
7. Action items:
   - [ ] Add load test for edge cases (1M row dataset)
   - [ ] Add linting rule to require indexes on WHERE clauses
   - [ ] Add monitoring alert for query slowness
```

(See deployment-and-incidents/02-incident-response-and-postmortems for full postmortem process.)

## Checklist

- [ ] Proximate cause identified (what went wrong)
- [ ] Root cause identified (why it went wrong)
- [ ] Regression test written (captures the exact bug)
- [ ] Guardrails added (prevents category of bug)
- [ ] Monitoring added (catches recurrence fast)
- [ ] Documentation updated (team knows about the issue)
- [ ] Postmortem completed (if production incident)

## Common Mistakes

1. **No regression test.** Fix a bug, but no test captures it. Bug recurs later.
2. **Fixing symptom, not root cause.** Restart service (symptom), but underlying query is still slow (root cause).
3. **No guardrails.** Fix the bug, but don't add assertions/validation to prevent similar bugs.
4. **Not sharing the learning.** You fixed a bug, but team doesn't know about it. Someone makes the same mistake later.
5. **Incident postmortem too short.** Just identify root cause, miss prevention opportunities.

