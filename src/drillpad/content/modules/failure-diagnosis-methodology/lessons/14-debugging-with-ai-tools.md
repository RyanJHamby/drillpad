# Debugging with AI Tools: The Partner, Not the Replacement

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Opportunity: AI as Debugging Partner

An AI assistant can help debug by:
- Explaining error messages
- Suggesting hypotheses
- Generating test code
- Reviewing your logic

**But:** AI can also mislead you with confident-sounding wrong answers.

## When to Use AI, When Not To

**Good use cases:**

```
1. Error message interpretation
   "What does this stack trace mean?"
   → AI explains the error
   
2. Hypothesis generation
   "Code looks fine to me, what could be wrong?"
   → AI suggests common causes
   
3. Code review
   "Does this look right to you?"
   → AI spots obvious issues
   
4. Test case generation
   "What test cases should I write?"
   → AI suggests edge cases
   
5. Pattern matching
   "I've seen this type of bug before, remind me how to fix it"
   → AI describes pattern
```

**Bad use cases:**

```
1. "Fix this for me"
   → AI might introduce new bugs
   → You won't understand the fix
   
2. "Validate my fix"
   → AI might be wrong
   → You need to verify independently
   
3. "This must be the root cause"
   → AI might hallucinate
   → Confirmation bias: you believe wrong answer
```

## The Protocol: Using AI for Debugging

**Step 1: State Your Hypothesis**

```
Bad:
  "I have a bug, can you fix it?"

Good:
  "I think it's an off-by-one error.
   Here's the code. Here's the test.
   Can you confirm if my hypothesis makes sense?"
```

Stating your hypothesis first prevents AI from implanting ideas.

**Step 2: Give Context**

```
Bad:
  "This code doesn't work"
  (No context, AI guesses)

Good:
  "Error: 'IndexError: list index out of range'
   Triggered by: test_pagination() with 100 items
   Expected: Get page 3 (10 items per page)
   Actual: Crash
   
   Here's the code: [code]
   
   My hypothesis: Off-by-one in page calculation
   Does this match what you see?"
```

More context = better AI response.

**Step 3: Verify the AI's Answer**

AI says: "The bug is on line 42, change `start = page * size` to `start = (page - 1) * size`"

Your verification:

```python
# Before (AI says this is wrong)
start = page * size

# Test:
page=3, size=10 → start = 30
# Items 30-39 (page 4), not page 3. Bug confirmed.

# After (AI's fix)
start = (page - 1) * size

# Test:
page=3, size=10 → start = 20
# Items 20-29 (page 3). Correct!

Conclusion: AI's answer is correct, and I verified it.
```

Never trust AI without verification.

**Step 4: Test the Fix**

```python
# AI's suggested fix:
start = (page - 1) * size

# Write a test to verify:
def test_pagination():
    # Page 1
    assert get_items(page=1, size=10) == items[0:10]
    
    # Page 2
    assert get_items(page=2, size=10) == items[10:20]
    
    # Page 3
    assert get_items(page=3, size=10) == items[20:30]
    
    # Edge case: Last page (partial)
    assert get_items(page=11, size=10) == items[100:105]  # Only 5 items

# Run test: Pass? Then fix is correct.
```

## Common AI Mistakes in Debugging

**Mistake 1: Confident-Sounding Hallucination**

```
You: "Why is this function returning None?"

AI: "It's because the global variable is not initialized.
    Add this line at the top: global my_var = []"

Reality: No such global variable exists in your code.
         AI invented it.
         
How to catch: Read the code yourself. Verify the AI's claim.
```

**Mistake 2: Oversimplification**

```
You: "Distributed system is slow. Where's the bottleneck?"

AI: "Probably the database. Add an index."

Reality: Could be:
  - Network latency (5 services, multiple jumps)
  - Cache miss (repeated queries)
  - Lock contention (concurrent writes)
  - Garbage collection (pause times)
  - Something else entirely
  
AI gave one answer, ignoring many possibilities.

How to catch: Don't accept first answer. Ask follow-ups.
```

**Mistake 3: Not Understanding Context**

```
You: "Code is slow. I'm using Python on a 1GB machine with 1 thread."

AI: "Add parallelization with multiprocessing."

Reality: With 1GB machine and threading/multiprocessing overhead,
         you might run out of memory.
         Maybe just optimize the algorithm instead.

How to catch: Tell AI your constraints upfront.
```

## Interview: Using AI in Live Debugging

**Q: "Can you use an AI assistant during interviews?"**

Check rules:
- Some companies allow: "You can use any tools"
- Some don't: "No external assistance"
- Most: "AI is OK for research, not for generating final code"

**If allowed, use it strategically:**

```
Scenario: 15-min debugging round

Time 0:00-1:00: Read error, understand problem (alone)
Time 1:00-3:00: Form hypothesis (alone)
Time 3:00-5:00: Ask AI: "Does this hypothesis make sense?"
Time 5:00-8:00: Use AI feedback (verify yourself)
Time 8:00-12:00: Implement fix (write code yourself)
Time 12:00-15:00: Test and verify (alone)
```

Interviewer wants to see:
- Your understanding (don't let AI think for you)
- Your verification (don't blindly trust AI)
- Your coding (don't copy-paste AI code)

**If you use AI:**
- Tell the interviewer: "I'm checking with an AI assistant on this hypothesis"
- Show your thinking: "AI suggests X, but I think Y because..."
- Verify independently: "Let me test this to confirm"
```

## Real Example: Using AI to Debug a Test

**Situation:** Your test is flaky (fails 5% of time).

**Step 1: Describe the issue to AI**

```
"I have a flaky test that fails intermittently.

Test code:
  def test_concurrent_writes():
      results = []
      
      def write():
          for i in range(100):
              shared_list.append(i)
              results.append(len(shared_list))
      
      t1 = Thread(target=write)
      t2 = Thread(target=write)
      t1.start()
      t2.start()
      t1.join()
      t2.join()
      
      assert len(results) == 200  # Fails 5% of time
  
The test should append 200 times total (100 per thread).
But sometimes results.append() is lost?"
```

**Step 2: AI Analysis**

AI might suggest:
- Race condition on results.append()
- Non-atomic list append in Python (GIL helps but doesn't guarantee)
- Use thread-safe queue instead

**Step 3: Verify**

```python
# AI's suggestion: results list isn't thread-safe

# Verify: Add lock
import threading
results_lock = threading.Lock()

def write():
    for i in range(100):
        shared_list.append(i)
        with results_lock:  # ← AI's fix: lock the list append
            results.append(len(shared_list))

# Test 100x: All pass now (not flaky)
# → AI's diagnosis was correct
```

## Checklist for AI-Assisted Debugging

- [ ] Hypothesis stated before asking AI
- [ ] Full context given (error, code, expected vs actual)
- [ ] AI's answer verified independently
- [ ] Test written to validate the fix
- [ ] Fix doesn't introduce new bugs
- [ ] Regression test added (prevents recurrence)

## Common Mistakes

1. **Trusting AI without verification.** AI says it's an off-by-one, you fix it, but the bug is actually elsewhere.
2. **AI-generated code not matching your style.** AI suggests code that's different from your codebase conventions (bad maintainability).
3. **Not understanding the fix.** AI explains the fix, you implement it, but you don't actually understand why it works.
4. **AI diverges the investigation.** AI suggests X, you believe it, and you spend 2 hours on X when the real bug is Y.
5. **Hiding AI use.** You use AI in an interview where it's not allowed, interviewer finds out (bad signal).

