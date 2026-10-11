# Reading Unfamiliar Code and Systems: The "Cold Start" Interview

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Interview Scenario

```
Interviewer: "Here's our codebase. You've never seen it before.
One feature is broken. The test is failing. Debug it in 30 minutes."

Your challenge:
- Don't know the architecture
- Don't know the conventions
- Don't know which files matter
- You're being timed
```

**The solution:** Systematic code reading. Not random wandering.

## Step 1: Find the Entry Point

Don't start by reading the entire codebase. Start by finding where the bug manifests.

```
Given: A failing test

Strategy:
  1. Read the test file (start here, not in main code)
     - What's it testing?
     - What's the expected behavior?
     - What's the actual behavior?
  
  2. Trace from test to code:
     - test_payment_processing() calls process_payment()
     - Where is process_payment() defined?
     - (Search codebase, or IDE: Go to Definition)
  
  3. Follow the error:
     - Test fails at: assert result.status == 'completed'
     - But result.status == 'failed'
     - Where does status get set?
     - Trace into process_payment() and find the assignment
```

## Step 2: Build a Mental Model (Box Diagram)

As you read code, draw a box diagram. Don't write down every line; write down relationships.

```
Payment Processing System (from reading code):

┌─ API Layer
│  ├─ POST /payments
│  └─ Calls: PaymentProcessor.process()
│
├─ PaymentProcessor
│  ├─ Validates input
│  ├─ Calls: PaymentGateway.charge()
│  └─ Updates: Database
│
├─ PaymentGateway (Stripe integration)
│  ├─ Makes HTTP request to Stripe
│  └─ Returns: success or error
│
└─ Database
   ├─ Stores: transactions table
   └─ Fields: id, amount, status, created_at
```

As you discover new components, add them to the diagram.

## Step 3: Trace the Data Flow

Follow one example through the entire system.

```
Example: User pays $10

Input: 
  POST /payments {"amount": 10, "card": "4111..."}

Trace:
  1. API layer receives request
     Payment(amount=10, card="4111...")
  
  2. PaymentProcessor.process(payment)
     - Validation: amount > 0? card valid?
     - Calls: stripe.charge(amount=10, source="4111...")
  
  3. Stripe API returns:
     {"status": "succeeded", "charge_id": "ch_abc123"}
  
  4. Database insert:
     INSERT INTO transactions (charge_id, amount, status)
     VALUES ("ch_abc123", 10, "completed")
  
  5. Return to user:
     {"status": "completed", "charge_id": "ch_abc123"}
```

Now you know the happy path. When test fails, which step breaks?

## Step 4: Tests as Documentation

Tests are the clearest documentation of how code should behave.

```
Failing test:
  def test_payment_processing():
      payment = Payment(amount=100, card="4111...")
      result = processor.process(payment)
      
      assert result.status == "completed"      # What's expected
      assert result.charge_id is not None      # What's expected

Test tells you:
  - Input: Payment object with amount and card
  - Output: Result with status and charge_id
  - Happy path: status should be "completed"

Now check: What's the actual output?
  - Is status set correctly?
  - Is charge_id populated?
  - Where does status come from?
```

## Step 5: The "I've Never Seen This Codebase" Protocol

When you have 30 minutes and don't know the code:

```
Time 0:00-2:00: Read the failing test
  - What's it testing?
  - What's expected?
  - What's actual?
  
Time 2:00-5:00: Find entry point
  - Where does code fail?
  - Locate the function/method
  - Read that function
  
Time 5:00-10:00: Build mental model
  - Which components are involved?
  - Box diagram: data flow
  - Which component likely has bug?
  
Time 10:00-20:00: Narrow hypothesis
  - Trace data through each component
  - Add logging/breakpoints
  - Narrow down which component
  
Time 20:00-28:00: Fix
  - Once found, fix is usually simple
  - Write regression test
  
Time 28:00-30:00: Verify
  - Test passes?
  - No new failures?
```

## Real Example: "Fix This Payment Bug"

**Failing test:**

```python
def test_refund_updates_wallet():
    transaction = Transaction(amount=100)
    refund = transaction.refund()
    
    assert refund.status == "completed"  # Fails here
    assert user.wallet.balance == original_balance + 100
```

**Your approach:**

Time 0:00: Read test
  → Expected: Refund status is "completed", wallet balance increased
  → Actual: (You don't know, run the test)

Time 1:00: Run test, see error
  → `AssertionError: assert 'pending' == 'completed'`
  → Status is 'pending', not 'completed'

Time 2:00: Find Transaction.refund() method
  ```python
  def refund(self):
      refund = Refund(amount=self.amount)
      refund.status = 'pending'  # ← Why is it pending?
      db.insert(refund)
      return refund
  ```

Time 3:00: Ah, status is set to 'pending'. Where should it be 'completed'?

Time 4:00: Look at similar code (charge method)
  ```python
  def charge(self):
      charge = Charge(amount=self.amount)
      charge.status = 'completed'  # ← It's synchronous!
      db.insert(charge)
      return charge
  ```

Time 5:00: Hypothesis: Refund should also be 'completed', not 'pending'

Time 6:00: Check if there's async processing
  - Grep for 'refund' in codebase
  - No async workers found
  - Hypothesis: Should be synchronous

Time 7:00: Fix

```python
def refund(self):
    refund = Refund(amount=self.amount)
    refund.status = 'completed'  # Changed from 'pending'
    db.insert(refund)
    return refund
```

Time 8:00: Test passes
Time 8:30: Write another regression test (edge cases)

Total time: 8.5 minutes (plenty of time left)

## Green Flags vs. Red Flags

**Green flags (you're on track):**
1. Test clearly shows what's expected vs. actual
2. Entry point is clear (test tells you which function)
3. Data flow is traceable (following a variable from input to output)
4. Mental model is simple (few components, clear relationships)

**Red flags (you're lost):**
1. Codebase is chaotic (no structure, unclear relationships)
2. Test is vague ("something is broken but don't know what")
3. Code path is unclear (function calls 10 things, hard to trace)
4. Multiple possible entry points (which function is actually called?)

If you hit red flags: Ask for help or guidance.

## Interview: Demonstrating Cold-Start Debugging

**Q: "You've never seen this codebase. A test is failing. What's your approach?"**

Weak answer:
```
"I'd read the code and try to understand it.
Maybe add some logging and see what happens."
(Vague, no strategy)
```

Strong answer:
```
"Systematic approach:

1. Read the failing test first
   - What does it test? What's expected?
   - This tells me what code I need to find
   
2. Find the entry point (the function being tested)
   - Use IDE: Go to Definition
   - Trace from test to code
   
3. Build a mental model as I read
   - Components involved?
   - Data flow?
   - Box diagram
   
4. Trace the happy path (one example through the system)
   - Input → process → output
   - Where does it diverge from expected?
   
5. Narrow to the broken component
   - Which component produces wrong output?
   - Which line of code?
   
6. Fix and verify
   - Simple fix once root cause found
   - Regression test captures the case
"
```

## Checklist

- [ ] Failing test read and understood
- [ ] Expected behavior identified
- [ ] Actual behavior identified (run test, see error)
- [ ] Entry point located (which function)
- [ ] Mental model sketched (box diagram)
- [ ] Data flow traced (one example)
- [ ] Component narrowed (where is bug)
- [ ] Root cause identified (which line)
- [ ] Fix is simple and testable

## Common Mistakes

1. **Starting with architecture.** Reading a 50-page design doc before reading the test. Start with the test.
2. **Not tracing one example.** Reading code without following data through it (abstract understanding without concrete example).
3. **Trying to understand everything.** Codebase has 100K lines. You don't need to understand all of it. Just the part relevant to the bug.
4. **Not building a mental model.** Reading code line by line without understanding relationships (you get lost in details).
5. **Giving up without narrowing.** "This code is too complex, I can't debug it." Instead: Narrow step by step.

