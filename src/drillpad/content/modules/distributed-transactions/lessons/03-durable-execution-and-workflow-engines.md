# Durable Execution & Workflow Engines (Temporal-Style)

## Firm Archetype: Temporal, Conductor, Zeebe, Step Functions

**Problem:** Long-running workflows (hours/days). Survive orchestrator crash, resume from failure point, maintain consistent state. Handle retries, timeouts, human approvals.

**Why hard:** State recovery (where in the workflow?), version upgrades (old definition vs new?), distributed tracing, side effects (replaying without re-sending).

---

## Event Sourcing & Workflow History

### Traditional Approach (State-Based)

```
Workflow: payment → shipping → notification

State:
  status: "processing"
  payment_status: "pending"
  shipping_status: null
  
Execution:
  1. Submit payment
  2. Wait for payment confirmation
  3. If confirmed: submit shipping
  4. Else: mark failed
  
Problem:
  ├─ Orchestrator crashes after payment confirmed
  ├─ Restart: does orchestrator know payment was confirmed?
  ├─ No: may retry payment (duplicate charge)
  └─ Solution: re-read payment status from payment service
  
Re-reading fails:
  ├─ Payment service slow/down
  ├─ Orchestrator: can't determine status
  └─ Result: stuck workflow
```

### Event-Sourced Approach (Temporal-Style)

```
Workflow history: immutable sequence of events

Events:
  - WorkflowStarted {timestamp, input}
  - ActivityScheduled {name: "payment", retries: 3}
  - ActivityCompleted {name: "payment", result: "charged"}
  - ActivityScheduled {name: "shipping"}
  - ActivityCompleted {name: "shipping", result: "shipped"}
  - WorkflowCompleted {output}

State is derived from history:
  ├─ Replay history: execute all events
  ├─ Current state: "shipping" (because payment completed, shipping pending)
  ├─ No need to query external services
  └─ Deterministic: same history = same state

Recovery:
  ├─ Orchestrator crashes
  ├─ Restart: read history from event store
  ├─ Replay: execute events up to failure point
  ├─ Resume: continue from "shipping" step
  └─ No duplicate work: payment not re-charged
```

---

## Deterministic Replay & Versioning

### Determinism Requirement

```
Workflow code must be deterministic:

Good (deterministic):
  def workflow():
    result1 = activity("payment", amount=100)  # Activity A
    if result1 > 0:
      result2 = activity("shipping")           # Activity B
    return result2

Bad (non-deterministic):
  def workflow():
    import random
    result1 = activity("payment", random.randint(1, 100))  # Random!
    return result1
    
    Problem:
      ├─ Initial run: random = 50
      ├─ Replay: random = 75 (different!)
      ├─ Activities don't match
      └─ State divergence (bad)

Bad (time-dependent):
  def workflow():
    current_time = datetime.now()  # Changes on replay!
    result = activity("pay", amount=current_time.second)
    return result

Rule:
  └─ All non-determinism must come from activities
     (payments, queries, etc.), not workflow code
```

### Code Versioning

```
Scenario: Upgrade workflow definition

Old version:
  def workflow():
    result1 = activity("payment")
    result2 = activity("shipping")
    return combine(result1, result2)

New version (added inventory check):
  def workflow():
    result1 = activity("payment")
    result_inv = activity("check_inventory")  # NEW
    result2 = activity("shipping")
    return combine(result1, result_inv, result2)

Running workflow:
  ├─ History: payment done, shipping pending
  ├─ On restart with new code
  ├─ Replay: payment → check_inventory (NEW STEP!)
  ├─ Problem: history doesn't have check_inventory event
  └─ Mismatch: crash

Solution 1: Versioning
  def workflow(version=1):
    if version >= 1:
      result1 = activity("payment")
    if version >= 2:
      result_inv = activity("check_inventory")
    result2 = activity("shipping")
    return combine(result1, result_inv, result2)
  
  On replay:
    ├─ Check: version at time of workflow creation
    ├─ Old workflows: replay with version=1
    ├─ New workflows: replay with version=2
    └─ Correct: no mismatch

Solution 2: Branching (easier)
  def workflow(old_payment_result=None):
    if not old_payment_result:
      result1 = activity("payment")
    else:
      result1 = old_payment_result
    
    result_inv = activity("check_inventory")
    result2 = activity("shipping")
    return combine(result1, result_inv, result2)
```

---

## Idempotency & Side Effects

### Activity Idempotency

```
Activity: charge credit card

First execution:
  ├─ Call payment API: charge($100)
  ├─ Returns: transaction_id = "txn_123"
  ├─ Side effect: customer charged $100

Workflow crashes, replayed:
  ├─ Replay: charge API call not re-executed (from history)
  ├─ History contains: "charge returned txn_123"
  ├─ Side effect: customer NOT charged again
  └─ Result: correct (charged once)

What if activity didn't persist result?

Workflow crashes, replayed:
  ├─ Re-execute: charge($100) again
  ├─ Payment API: charges another $100 (duplicate!)
  └─ Result: bad (charged twice)

Prevention:
  ├─ Idempotency key: include UUID with charge request
  ├─ Payment API: deduplicates by key
  ├─ Re-execute with same key: returns cached result (no charge)
  └─ Result: safe (charged once)
```

### Orchestrator Storage

```
Event store (append-only log):
  
  Workflow execution: payment_workflow_123
  
  Events:
    [1] WorkflowStarted {id, timestamp}
    [2] ActivityScheduled {activity: "payment", idempotency_key: "uuid1"}
    [3] ActivityCompleted {activity: "payment", result: txn_123}
    [4] ActivityScheduled {activity: "shipping", idempotency_key: "uuid2"}
    [5] ActivityCompleted {activity: "shipping", result: tracking_id}
    [6] WorkflowCompleted {output}

Replay to event 4:
  ├─ Execute workflow code
  ├─ Encounter: activity("payment")
  ├─ Check history: event [3] has result
  ├─ Don't call payment API again
  ├─ Return cached result: txn_123
  ├─ Continue: activity("shipping")
  ├─ Check history: no event for shipping yet
  ├─ Call shipping API (this is where we failed)
  └─ On success: append event [5] to history
```

---

## Timers & Timeouts

```
Workflow: send order → wait 7 days → send reminder

Code:
  def workflow():
    result = activity("send_order")
    # Wait 7 days
    result2 = activity("send_reminder")
    return result2

Timeout handling:
  ├─ Schedule timer: 7 days from now
  ├─ Timer ID: unique, derived from workflow + step
  ├─ On expiry: timer event appended to history
  ├─ Workflow resumes from timer point

Events:
  [1] WorkflowStarted
  [2] ActivityScheduled {send_order}
  [3] ActivityCompleted {result}
  [4] TimerScheduled {duration: 604800 sec, id: "wait_1"}
  [5] TimerFired {id: "wait_1"}  ← fires after 7 days
  [6] ActivityScheduled {send_reminder}
  [7] ActivityCompleted
  [8] WorkflowCompleted

Cancellation:
  ├─ Workflow: cancel_order()
  ├─ Cancel timer: [4] → cancelled
  ├─ Workflow continues: skip to cleanup
```

---

## Scale & Failure Modes

### Storage

```
Workflow event store:

1M workflows/day
Average events: 20 per workflow
Total events: 1M * 20 = 20M events/day

Event size: 500 bytes
Total storage: 20M * 500 = 10 GB/day
Retention: 90 days = 900 GB

Optimize:
  ├─ Compress: zstd (50% reduction)
  ├─ Archive: old workflows to cold storage
  └─ Cost: ~$10/month for Postgres
```

### Orchestrator Crash

```
Scenario: Orchestrator crashes mid-workflow

Detection:
  ├─ Heartbeat: orchestrator → event store (every 10 sec)
  ├─ Timeout: no heartbeat for 30 sec
  ├─ Manager: reassign workflow to new orchestrator

Recovery:
  ├─ New orchestrator picks up workflow
  ├─ Reads history from event store
  ├─ Replays events to determine state
  ├─ Resumes from last completed step
  └─ Time: ~10 sec (detection) + replay time (~1 sec)

Guarantee:
  └─ No duplicate execution (events are source of truth)
```

### Stuck Workflow

```
Scenario: Activity never completes (waits for external event)

Detection:
  ├─ Heartbeat monitoring: activity > 1 hour
  ├─ Alert: activity appears stuck
  └─ Action: manual intervention

Options:
  ├─ Retry: schedule new attempt
  ├─ Override: manually provide result
  ├─ Rollback: cancel workflow, compensate
  └─ Timeout: set deadline for activity
```

---

## Code Example (Simple Temporal-Like Engine)

```python
import time
from dataclasses import dataclass
from typing import Any, List, Dict
import json

@dataclass
class WorkflowEvent:
    type: str  # "started", "activity_scheduled", "activity_completed", etc.
    timestamp: float
    details: Dict[str, Any]

class WorkflowHistory:
    def __init__(self):
        self.events: List[WorkflowEvent] = []
    
    def append_event(self, event_type: str, details: Dict):
        event = WorkflowEvent(
            type=event_type,
            timestamp=time.time(),
            details=details
        )
        self.events.append(event)
        return event
    
    def get_activity_result(self, activity_name: str):
        """Get result from history if activity already executed."""
        for event in reversed(self.events):
            if event.type == "activity_completed" and \
               event.details.get("activity") == activity_name:
                return event.details.get("result")
        return None

class WorkflowExecutor:
    def __init__(self):
        self.history = WorkflowHistory()
        self.activities_executed = set()
    
    def execute_activity(self, name: str, *args, **kwargs):
        """Execute activity (from cache or fresh)."""
        # Check history
        cached = self.history.get_activity_result(name)
        if cached:
            return cached
        
        # Execute (external call)
        result = self._call_activity(name, *args, **kwargs)
        
        # Record
        self.history.append_event("activity_completed", {
            "activity": name,
            "result": result
        })
        self.activities_executed.add(name)
        
        return result
    
    def _call_activity(self, name: str, *args, **kwargs):
        """Call external activity (simulated)."""
        print(f"Executing activity: {name}")
        return f"result_{name}"
    
    def schedule_timer(self, duration_sec: int, callback):
        """Schedule timer."""
        self.history.append_event("timer_scheduled", {
            "duration": duration_sec
        })
        # In practice: use event loop
        time.sleep(duration_sec)
        self.history.append_event("timer_fired", {})
        callback()
    
    def get_state(self):
        """Derive state from history."""
        return {
            "events": len(self.history.events),
            "activities_executed": list(self.activities_executed),
            "last_event": self.history.events[-1].type if self.history.events else None
        }

# Example workflow
def payment_workflow(executor):
    """Workflow: charge → ship → notify."""
    executor.history.append_event("workflow_started", {})
    
    # Step 1: charge
    charge_result = executor.execute_activity("charge_payment", amount=100)
    print(f"Charged: {charge_result}")
    
    # Step 2: ship
    ship_result = executor.execute_activity("ship_order", tracking_id="track_123")
    print(f"Shipped: {ship_result}")
    
    # Step 3: wait & notify
    executor.schedule_timer(
        duration_sec=5,  # 5 sec instead of 7 days for demo
        callback=lambda: executor.execute_activity("send_notification", msg="Order shipped!")
    )
    
    executor.history.append_event("workflow_completed", {
        "output": "success"
    })
    
    return "success"

# Test
executor = WorkflowExecutor()
result = payment_workflow(executor)
print(f"\nWorkflow state: {executor.get_state()}")
print(f"History: {len(executor.history.events)} events")
```

---

## Interview Checklist

- [ ] Event sourcing for durability (history-based state)
- [ ] Deterministic replay (no random, no time)
- [ ] Activity idempotency + deduplication
- [ ] Versioning workflows (old vs new definitions)
- [ ] Timers and timeouts
- [ ] Failure recovery (replay from last event)
- [ ] Side effects (charges, notifications)
- [ ] Scale: 1M workflows, 20M events/day

## Common Wrong Answers

- ❌ "Just save current state" — can't recover without replaying
- ❌ "Non-deterministic workflow code" — replay fails, state diverges
- ❌ "No idempotency keys" — duplicate charges on retry
- ❌ "Immediate retry on failure" — thundering herd
- ❌ "No versioning" — old workflows fail with new code
- ❌ "Don't track side effects" — duplicate work/charges
