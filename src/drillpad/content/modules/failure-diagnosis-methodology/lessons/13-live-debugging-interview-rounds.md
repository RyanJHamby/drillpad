# Live Debugging Interview Rounds: The Protocol

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Interview Format

```
Interviewer: "I'm going to give you a buggy program.
You have 15 minutes. Debug it."

Your task:
  1. Read the error message
  2. Form 2-3 hypotheses
  3. Choose a test that discriminates
  4. Find the bug
  5. Write a minimal fix
  6. Add a regression test
```

## The Protocol

**Time 0:00-0:30: Read the Error**

```
Buggy code:
  def find_item(items, target):
      for i in range(len(items)):
          if items[i] == target:
              return i
      return -1

Test:
  items = [1, 2, 3]
  result = find_item(items, 2)
  assert result == 1  # Expected: 1, Actual: ???
  
Error message: AssertionError: assert 3 == 1
```

State what you know:
  - Expected: 1 (index of element 2)
  - Actual: 3 (???)
  - Something is off by 2

**Time 0:30-1:00: Restate the Problem**

```
"OK, so find_item([1, 2, 3], 2) returns 3, but we expect 1.
The function is supposed to return the index of the target element.
Index 1 is where element 2 is located.
But it's returning 3 instead."
```

(Shows you understood the problem)

**Time 1:00-2:00: Form Hypotheses**

```
Hypothesis A: Off-by-one error (index calculation)
Hypothesis B: Wrong comparison operator (== vs !=)
Hypothesis C: Wrong return value (returning length instead of index)

Which is most likely?
  Returning 3 when expecting 1 → could be len(items) - 1
  → Hypothesis C seems likely
```

**Time 2:00-5:00: Design a Test That Discriminates**

```
Test hypothesis C: "Returns length instead of index"
  
Test case:
  items = [1, 2, 3]
  result = find_item(items, 2)
  
Expected if C true: result == len(items) == 3 ✓ (matches actual)
Expected if A true: result == 0 or 2 (not 3)
Expected if B true: result == -1 (not found)

So test C: Add print statement to see what's happening
  print(f"Found at {i}, returning {i}")
  
Or: Test with list of different length
  items = [10, 20]
  result = find_item(items, 20)
  If C true: result == 2
  If A true: result == 1
```

**Time 5:00-10:00: Narrow Down**

```
Read the code carefully:
  def find_item(items, target):
      for i in range(len(items)):
          if items[i] == target:
              return i       ← Looks right
      return -1              ← Looks right
  
Actually, code looks correct!
Maybe the test is wrong?
  
Run mentally:
  items = [1, 2, 3]
  target = 2
  
  i=0: items[0]=1, 1==2? No
  i=1: items[1]=2, 2==2? Yes → return 1
  
Expected: 1
But actual is 3?

Wait. Let me check the test again:
  assert result == 1  # Expected: 1, Actual: ???

Maybe the error message is wrong?
Or the code was different when called?

Ask interviewer: "Can you show me the exact code and test?"
```

**Time 10:00-13:00: Fix**

Once you find the bug (in this case, code is correct, test setup might be wrong):

```
If this were an off-by-one error:

Wrong:
  def find_item(items, target):
      for i in range(len(items)-1):  ← Off by one!
          ...

Fix:
  def find_item(items, target):
      for i in range(len(items)):
          ...

Or if it was returning length:

Wrong:
  def find_item(items, target):
      for i in range(len(items)):
          if items[i] == target:
              return len(items)  ← Wrong!
      return -1

Fix:
  def find_item(items, target):
      for i in range(len(items)):
          if items[i] == target:
              return i  ← Correct
      return -1
```

**Time 13:00-15:00: Regression Test**

```python
def test_find_item():
    # Original bug case
    assert find_item([1, 2, 3], 2) == 1
    
    # Edge cases
    assert find_item([1], 1) == 0  # Single element
    assert find_item([1, 2, 3], 1) == 0  # First element
    assert find_item([1, 2, 3], 3) == 2  # Last element
    assert find_item([1, 2, 3], 4) == -1  # Not found
```

## Common Planted Bugs (Interview Examples)

### Bug 1: Off-by-One in Loop

```python
def sum_array(arr):
    total = 0
    for i in range(len(arr)-1):  # ← Off by one!
        total += arr[i]
    return total

# Test
assert sum_array([1, 2, 3, 4]) == 10
# Expected: 1+2+3+4 = 10
# Actual: 1+2+3 = 6 (missing last element)
```

Root cause: `range(len(arr)-1)` excludes last element.

**Fix:** `for i in range(len(arr))`

### Bug 2: Mutation/Aliasing

```python
def append_to_list(lst, item):
    lst.append(item)  # Modifies original!
    return lst

original = [1, 2]
result = append_to_list(original, 3)
assert original == [1, 2]  # ← Fails! Original was modified
# Actual: [1, 2, 3]
```

Root cause: Function modifies input (aliasing).

**Fix:** `new_lst = lst.copy(); new_lst.append(item); return new_lst`

### Bug 3: Shared Mutable Default

```python
def add_item(item, items=[]):  # ← Shared default!
    items.append(item)
    return items

list1 = add_item(1)
list2 = add_item(2)

assert list1 == [1]  # ← Fails!
# Actual: [1, 2] (shared with list2)
```

Root cause: Mutable default argument shared across calls.

**Fix:** `def add_item(item, items=None): if items is None: items = []; ...`

### Bug 4: Integer Overflow/Truncation

```python
def multiply_prices(price1, price2):
    # Prices are floats (e.g., 19.99), multiply them
    result = int(price1 * price2)  # ← Truncates!
    return result

assert multiply_prices(10.5, 2.5) == 26
# 10.5 * 2.5 = 26.25
# int(26.25) = 26 ✓
# But multiplying 0.1 * 0.1 = 0.01 → int(0.01) = 0 ✗
# (Loses precision)
```

Root cause: Truncation instead of rounding.

**Fix:** `return round(price1 * price2, 2)`

### Bug 5: String Comparison

```python
def is_positive(num_str):
    return num_str > "0"  # ← String comparison!

assert is_positive("10")  # "10" > "0"? Lexicographic!
# Actual: True (correct by accident)

assert is_positive("9")  # "9" > "0"? 
# Lexicographic: "9" > "0" = True (correct)

assert is_positive("2")  # "2" > "0"?
# Lexicographic: "2" > "0" = True (correct)

But:
assert is_positive("-5")  # "-5" > "0"?
# Lexicographic: "-" comes before "0"
# Returns False (wrong! -5 is negative, should be False, but for wrong reason)
```

Root cause: String comparison instead of numeric.

**Fix:** `return int(num_str) > 0`

### Bug 6: Iterator Invalidation

```cpp
#include <vector>
for (auto it = vec.begin(); it != vec.end(); ++it) {
    if (*it == 5) {
        vec.erase(it);  // ← Iterator invalidated!
    }
}
// After erase, iterator is invalid
// Continuing loop → undefined behavior
```

Root cause: Erasing while iterating.

**Fix:** 
```cpp
for (auto it = vec.begin(); it != vec.end(); ) {
    if (*it == 5) {
        it = vec.erase(it);  // erase returns next valid iterator
    } else {
        ++it;
    }
}
```

### Bug 7: Float Precision

```python
def is_equal(a, b):
    return a == b  # ← Exact equality!

assert is_equal(0.1 + 0.2, 0.3)
# 0.1 + 0.2 = 0.30000000000000004 (floating point error)
# 0.3 = 0.3
# 0.30000000000000004 != 0.3 → False
```

Root cause: Floating point comparison needs tolerance.

**Fix:** `return abs(a - b) < 1e-9`

### Bug 8: Race on Counter

```python
counter = 0

def increment():
    global counter
    for _ in range(1000):
        counter += 1  # ← Race condition!

import threading
t1 = threading.Thread(target=increment)
t2 = threading.Thread(target=increment)
t1.start()
t2.start()
t1.join()
t2.join()

assert counter == 2000
# Actual: Random value < 2000 (race condition)
```

Root cause: Non-atomic read-modify-write.

**Fix:** Use lock
```python
import threading
counter = 0
lock = threading.Lock()

def increment():
    global counter
    for _ in range(1000):
        with lock:
            counter += 1
```

## Interview Soft Skills

**During the debug session:**

1. **Think out loud**
   - "I'm reading the code... I see a loop... let me trace through it"
   - Interviewer can correct you before you go too far

2. **Ask clarifying questions**
   - "What's the exact error message?"
   - "Can you run it again and show me the output?"

3. **Be systematic**
   - Don't guess randomly
   - Form hypotheses, test them
   - Show your work

4. **If stuck, ask for hints**
   - "I've been debugging for 10 minutes and haven't found it. Can I have a hint?"
   - Shows good judgment (know when to escalate)

5. **Fix small issues**
   - Once you find the bug, fix it
   - Don't over-engineer (unless asked)

## Checklist for Live Debugging Round

- [ ] Restate the problem (show you understand)
- [ ] Form 2-3 hypotheses (don't jump to conclusion)
- [ ] Design a test that discriminates (narrate your thinking)
- [ ] Find the bug (walk through code or run it)
- [ ] Write minimal fix (don't refactor)
- [ ] Add regression test (captures the case)
- [ ] Verify fix (test should pass)

## Common Interview Mistakes

1. **Not restating the problem.** Jump straight to code, miss what's actually wrong.
2. **Too many hypotheses.** "It could be X or Y or Z or A or B..." Pick 2-3.
3. **Not showing work.** Silent for 10 minutes, then "I found it!" → Interviewer can't help.
4. **Over-fixing.** Find off-by-one, then refactor entire function.
5. **No regression test.** Fix the bug but don't capture it in a test.

