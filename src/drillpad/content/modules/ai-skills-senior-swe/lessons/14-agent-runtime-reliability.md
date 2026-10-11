# Agent Runtime Reliability: Durable Workflows, Idempotency, Tool Failure Handling

## Why This Interview Matters

Building agents (LLM + tool calls) is different from building stateless APIs. Agents must **survive partial failures, retry tool calls, and guarantee exactly-once semantics.** This is critical for any role building AI systems, agents, or durable workflows.

**Core insight:** Tool calls are unreliable. The network might fail, the tool might crash, or the agent might crash mid-execution. You need idempotency + durability to handle this.

---

## First Principle: Agent Execution and Failure Modes

A simple agent has this lifecycle:

```
Agent execution:
1. User asks: "Transfer $100 to Alice"
2. Agent calls LLM: "What do I do?"
3. LLM responds: "Use tool transfer_money(amount=100, recipient=Alice)"
4. Agent calls tool: transfer_money(100, "Alice")
5. Tool returns: {status: success, transaction_id: 12345}
6. Agent calls LLM: "Tool says success, transaction ID 12345. What next?"
7. LLM responds: "Tell user: transfer complete"
8. Agent returns: "Transfer complete, transaction ID 12345"
```

**Failure point 1: Network failure after step 4 (tool executed, but response lost)**

```
1-4: Succeed
5: Network timeout
   Tool HAS executed (money transferred)
   Agent didn't get response
   Agent retries: transfer_money(100, "Alice") AGAIN
   
Result: Double charge! $200 transferred instead of $100.
```

**Failure point 2: Tool crashes mid-execution**

```
1-4: Agent calls tool
5: Tool process crashes
   Money partially transferred (DB write partial)
   Tool doesn't respond
   Agent retries
   
Result: Inconsistent state. Money transferred twice, once incomplete.
```

**Failure point 3: Agent crashes mid-workflow**

```
1-6: LLM planning succeeds
7: Agent process crashes (killed by scheduler)
   User never sees result
   Tool has already executed
   Next retry doesn't know tool was already called
   
Result: Lost confirmation, potential duplicate execution on retry.
```

---

## Solution 1: Idempotency (Critical for Tool Calls)

A tool is **idempotent** if calling it twice produces the same result as calling it once:

```
def transfer_money(amount, recipient, idempotency_key):
  # Check if already processed
  existing = db.query(
    "SELECT * FROM transfers WHERE idempotency_key = ?",
    idempotency_key
  )
  
  if existing:
    # Already processed, return same result
    return {
      'status': 'success',
      'transaction_id': existing.transaction_id,
      'amount': existing.amount,
    }
  
  # First call: execute
  txn_id = generate_transaction_id()
  db.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", amount, account_id)
  db.execute(
    "INSERT INTO transfers (idempotency_key, transaction_id, amount) VALUES (?, ?, ?)",
    idempotency_key, txn_id, amount
  )
  
  return {
    'status': 'success',
    'transaction_id': txn_id,
    'amount': amount,
  }
```

**How to use idempotency key:**

```
Agent calls:
  transfer_money(amount=100, recipient="Alice", idempotency_key="agent-run-12345-step-1")
  
Network timeout (but tool succeeded)
  Agent retries with SAME idempotency_key
  Tool: "I've seen this key before, returning cached result"
  Result: No double charge
  
Cost: Extra DB lookup (~1ms) instead of $100 duplicate charge
```

**Idempotency guarantees:**
- Same input (including idempotency_key) → same output ✓
- No side effects (money transferred) on retry ✓
- Tool can fail/retry safely ✓

---

## Solution 2: Durable Workflow State

Store the entire workflow in persistent state:

```
Workflow state:

{
  workflow_id: "wf-12345",
  user_request: "Transfer $100 to Alice",
  steps: [
    {
      step_id: 1,
      action: "call_llm",
      input: {prompt: "..."},
      output: {tool_call: "transfer_money(...)"},
      status: "completed",
      timestamp: "2024-01-10T10:00:00Z",
    },
    {
      step_id: 2,
      action: "call_tool",
      input: {tool: "transfer_money", args: {amount: 100, recipient: "Alice"}},
      tool_result: {status: "success", transaction_id: 12345},
      status: "completed",
      timestamp: "2024-01-10T10:00:01Z",
      idempotency_key: "wf-12345-step-2",  // For retries
    },
    {
      step_id: 3,
      action: "call_llm",
      input: {prompt: "Tool returned...", context: [...previous steps...]},
      output: {text: "Transfer complete"},
      status: "completed",
      timestamp: "2024-01-10T10:00:02Z",
    }
  ],
  status: "completed",
  result: "Transfer complete, transaction ID 12345"
}
```

**Workflow persistence:**

```python
class DurableWorkflow:
  def __init__(self, workflow_id, db):
    self.workflow_id = workflow_id
    self.db = db
    self.state = self.load_state()
  
  def load_state(self):
    return self.db.get(f"workflow:{self.workflow_id}")
  
  def save_state(self):
    self.db.set(f"workflow:{self.workflow_id}", self.state)
  
  def execute_step(self, step_id, action, input_data):
    # Check if step already completed
    existing = self.find_step(step_id)
    if existing and existing.status == "completed":
      return existing.output
    
    # Execute step
    output = self._do_action(action, input_data)
    
    # Save to state
    step = {
      'step_id': step_id,
      'action': action,
      'input': input_data,
      'output': output,
      'status': 'completed',
      'timestamp': now(),
    }
    self.state['steps'].append(step)
    self.save_state()  # Persist immediately
    
    return output
  
  def recover_from_crash(self):
    # If workflow crashed, find where it stopped
    last_completed = max(
      [s for s in self.state['steps'] if s['status'] == 'completed'],
      key=lambda s: s['step_id']
    )
    return last_completed.step_id + 1
```

**Recovery after crash:**

```
Workflow crashes at step 5 (out of 8 steps)
  Agent restarts
  Loads workflow state from DB
  Finds: steps 1-4 completed
  Resumes: step 5
  
Cost: Only retry step 5+, not entire workflow
```

---

## Solution 3: Tool Failure Handling and Retries

Tools can fail. How to handle?

```
Tool outcomes:
1. Success: Tool executed, returned result
2. Retriable failure: Network timeout, temporary service down
3. Non-retriable failure: Invalid arguments, permission denied
4. Timeout: Tool took too long

Agent strategy per outcome:
  1. Success: Continue workflow
  2. Retriable: Retry (exponential backoff)
  3. Non-retriable: Escalate to user
  4. Timeout: Either retry or escalate (depends on tool)
```

**Implementation:**

```python
class AgentToolExecutor:
  def execute_tool(self, tool_name, args, idempotency_key):
    max_retries = 3
    base_delay = 1.0  # seconds
    
    for attempt in range(max_retries):
      try:
        # Call tool with timeout
        result = call_tool_with_timeout(
          tool_name, args, idempotency_key,
          timeout_seconds=30
        )
        return {
          'status': 'success',
          'result': result,
          'attempt': attempt + 1,
        }
      except TimeoutError:
        # Timeout: log, then retry
        delay = base_delay * (2 ** attempt)  # Exponential backoff
        logger.warning(f"Tool {tool_name} timeout, retry {attempt+1} in {delay}s")
        time.sleep(delay)
      except PermissionError as e:
        # Non-retriable: don't retry
        return {
          'status': 'failed',
          'error': str(e),
          'attempt': attempt + 1,
          'retriable': False,
        }
      except Exception as e:
        # Other error: might be retriable, might not
        if is_retriable(e):
          delay = base_delay * (2 ** attempt)
          logger.warning(f"Tool {tool_name} retriable error, retry in {delay}s")
          time.sleep(delay)
        else:
          return {
            'status': 'failed',
            'error': str(e),
            'attempt': attempt + 1,
            'retriable': False,
          }
    
    # Exhausted retries
    return {
      'status': 'failed',
      'error': f'Tool {tool_name} failed after {max_retries} retries',
      'attempt': max_retries,
      'retriable': True,
    }
```

**Retry strategy:**
- Exponential backoff: 1s, 2s, 4s, 8s, ... (prevents thundering herd)
- Jitter: Add randomness (1s ± 200ms) to avoid synchronized retries
- Max retries: Usually 3-5 for retriable errors
- Timeout: 30 seconds per tool call (adjust per tool)

---

## Solution 4: Sandbox Isolation and Permission Models

Tools can be dangerous. Isolate them:

```
Process boundary:
  Main agent process: Untrusted LLM can request tools
  Sandbox process: Runs tool in isolated container
  
Tool call flow:
  1. Agent process: "Run transfer_money(100, Alice)"
  2. RPC to sandbox: Send request
  3. Sandbox: Execute tool (can't access agent memory, config, etc.)
  4. Sandbox: Return result
  5. Agent process: Receive result

Benefit:
  If tool crashes, agent continues (process boundary)
  If tool tries memory access exploit, fails (sandboxed)
  If tool tries to read sensitive files, fails (permissions)
```

**Permission model:**

```python
class ToolPermission:
  def __init__(self, tool_name):
    self.tool_name = tool_name
    self.allowed_resources = []
    self.denied_resources = []
  
  def allow_resource(self, resource_pattern):
    self.allowed_resources.append(resource_pattern)
  
  def deny_resource(self, resource_pattern):
    self.denied_resources.append(resource_pattern)
  
  def can_access(self, resource):
    # Check deny list first
    if any(matches(resource, pattern) for pattern in self.denied_resources):
      return False
    # Then check allow list
    if any(matches(resource, pattern) for pattern in self.allowed_resources):
      return True
    return False

# Example:
transfer_permission = ToolPermission('transfer_money')
transfer_permission.allow_resource('accounts:*')
transfer_permission.deny_resource('accounts:admin:*')  # Can't access admin accounts

# Tool can transfer money for users, not for admin accounts
```

---

## Failure Scenarios and Recovery

### Scenario 1: Network Timeout After Tool Execution

```
Agent calls: transfer_money(100, Alice)
Tool executes: Money transferred
Network fails: Response never reaches agent
Agent timeout: Assumes tool failed

Recovery (with idempotency):
  Agent retries: transfer_money(100, Alice, idempotency_key=X)
  Tool: "I've seen key X before, returning cached result"
  Result: Correct (no double charge)

Recovery (without idempotency):
  Agent retries: Money transferred AGAIN
  Result: Double charge (disaster)
```

### Scenario 2: Agent Crashes Mid-Workflow

```
Agent executing workflow (5 steps)
Step 3 completes: Tool execution succeeded
Agent saves state: Step 3 marked "completed"
Step 4: Agent crashes before calling tool

Recovery:
  Agent restarts
  Loads workflow from DB
  Sees steps 1-3 completed
  Resumes: Step 4
  Steps 5 executes and completes
  
Result: Correct workflow (no duplicate step 3)
```

### Scenario 3: Tool Becomes Unavailable

```
Agent calls: search_api(query="...")
Tool: Service down, returns 503 error

Agent strategy:
  1st attempt: 503, retriable, wait 1s
  2nd attempt: 503, retriable, wait 2s
  3rd attempt: 503, retriable, wait 4s
  4th attempt: 503, exhausted retries
  
Action:
  Return to user: "Search temporarily unavailable, try again in 1 minute"
  Log for monitoring: Alert ops that search_api is down
```

---

## Monitoring and Observability

What metrics matter for agent reliability?

```
Per-workflow metrics:
  - Completion rate (% of workflows that complete)
  - Average steps to completion
  - Time to completion
  - % of workflows with retries (indicator of failure)
  - % of workflows that failed permanently

Per-tool metrics:
  - Call success rate
  - Retry rate
  - Average latency
  - p99 latency
  - Timeout frequency
  - Error types (timeout, permission, network, etc.)

Example dashboard:
  transfer_money tool:
    - 99.9% success rate (excellent)
    - p99 latency: 150ms
    - Retry rate: 0.1% (very low)
    - Most common error: Timeout (0.05%)
  
  search_api tool:
    - 95% success rate (mediocre)
    - p99 latency: 5000ms (slow)
    - Retry rate: 5% (high, indicates unreliability)
    - Most common error: Timeout (3%), Service unavailable (2%)
```

---

## Interview Q&A

**Recall 1:** Why is idempotency important for agent tool calls?

*Must-say:*
- Networks are unreliable. Tool may execute but response is lost.
- Without idempotency, agent retries cause duplicate execution (double charge).
- With idempotency (using idempotency_key), retry returns same result, no side effects.

**Probe 1:** Agent workflow crashes at step 5 of 10. How do you recover?

*Expected:*
- Persist workflow state to DB after each step.
- On restart, load state from DB, resume at step 5.
- Cost: Only retry step 5+, not entire workflow.
- Alternative (bad): No persistence, restart from step 1.

**Probe 2:** Tool times out. Should the agent retry?

*Expected:*
- Depends on idempotency of the tool.
- If idempotent: Safe to retry.
- If not idempotent: Risky; check if it already executed (log, audit trail).
- Best practice: Make all tools idempotent.

**Numeric 1:** Agent makes 10 tool calls per workflow. Each tool has 99.9% success rate. What's the probability that entire workflow succeeds?

*Working:*
- P(all succeed) = 0.999^10 = 0.9900 = 99.0%
- P(at least one fails) = 1 - 0.9900 = 1.0% = 1 in 100 workflows fails
- With 1000 workflows/day: 10 failures/day

**Numeric 2:** Tool timeout is 10 seconds. Agent retries with exponential backoff (1s, 2s, 4s). How long until 3rd retry?

*Working:*
- 1st attempt: 10s timeout
- 2nd attempt: 1s wait + 10s timeout = 11s
- 3rd attempt: 2s wait + 10s timeout = 12s
- Total: 10 + 11 + 12 = 33 seconds

---

## Checklist: Robust Agent Execution

- [ ] **All tools are idempotent (or have idempotency_key support).** No double charges.
- [ ] **Workflow state persists to DB.** Each step saved after completion.
- [ ] **Tool calls include timeout (30s default).** Fail fast, don't hang forever.
- [ ] **Retries use exponential backoff.** 1s, 2s, 4s (max 3-5 attempts).
- [ ] **Tools run in sandbox (separate process/container).** Failure isolation.
- [ ] **Permission model restricts tool access.** Tool can't read config, private keys, etc.
- [ ] **Monitoring tracks success rate per tool.** Alert if tool success < 95%.
- [ ] **Crash recovery is tested.** Kill agent mid-workflow, verify resume works.

### Common Wrong Answers

- "I'll retry immediately if tool fails." ← No, use backoff to avoid overwhelming service.
- "I'll trust the LLM to handle failures." ← No, LLM can't see tool output if network fails.
- "Idempotency is only for payments." ← No, every tool should be idempotent (email, DB, etc.).
- "Tool crashes are fine, agent will retry." ← No, retries might hit same crash; need monitoring.

---

## Story Card: Slack Message Agent Gone Wrong

**Context:** Agent sends messages to Slack via `send_message(channel, text)` tool.

**Incident (no idempotency):**
```
Agent calls: send_message(channel="alerts", text="Server down!")
Tool executes: Message posted to Slack
Network timeout: Response never reaches agent

Agent retries (no idempotency_key):
  Tool executes again
  Message posted to Slack TWICE

Result: "Server down!" appears twice in Slack
  Looks like duplicate alert
  On-call engineer confused
  
Cascading: Agent keeps retrying (3 times)
  Message appears 3 times
  Slack flooded with duplicates
  Noise, reduced signal
```

**Post-incident (with idempotency):**
```
Agent calls: send_message(channel="alerts", text="Server down!", idempotency_key="agent-wf-123-step-2")
Tool executes: Message posted, idempotency_key stored
Network timeout: Response never reaches agent

Agent retries (SAME idempotency_key):
  Tool checks: "I've seen this key before"
  Returns: {status: success, message_id: 12345}
  NO new message posted

Result: Message appears once
  On-call engineer sees single alert
  Takes action
```

**Lesson:** Idempotency prevents cascading failures even in "simple" operations.

---

## Further Study

- **AWS Step Functions**: Durable workflows, built-in retry logic
- **Temporal**: Durable workflow engine for complex agents
- **LLM agents (ReAct paper)**: Foundation for reasoning agents
- **Stripe API design**: Best practices for idempotency in APIs (apply to tools)
