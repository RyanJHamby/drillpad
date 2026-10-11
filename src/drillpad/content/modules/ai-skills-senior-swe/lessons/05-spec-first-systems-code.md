# Spec-First Development: Agents and Systems Code

## Why This Is Different

In SaaS: "give the agent a rough description, let it iterate toward a working solution" works fine. Code gets tested, fixed, shipped.

In systems code (Rust/C++ near trust boundaries, trading latency-critical paths, anything where a subtle bug costs more than the feature): "rough description" is exactly how disasters happen.

**The highest-leverage move is writing a precise spec *before* directing an agent to implement anything.**

## What "Spec" Means Here (Not An Academic Textbook)

```
A real spec for this domain includes:

1. INVARIANTS (not just behavior)
   Instead of: "the network path shouldn't be reused"
   Write: "At all times, leased[p] == true implies exactly one holder
           exists for path p, and no operation may transition leased[p]
           from false to true without first acquiring an exclusive lock"

2. FAILURE MODES (not just happy path)
   "On timeout: deny the invocation and emit audit log code X"
   Not: "handle errors appropriately"

3. CONCURRENCY REQUIREMENTS (explicit)
   "Single-threaded OR thread-safe via Mutex on state object?
   Guarantee that thread A and B cannot race here HOW exactly?"

4. NON-GOALS (what this task is NOT)
   "This does not handle network partition recovery.
    This does not implement automatic retry."

5. UNSAFE BOUNDARIES (if any)
   "This task may need FFI to C. Mark the boundary explicitly."
```

## The Failure Mode: SaaS-Shaped Instincts in Systems Code

Agents default to:
- `.unwrap()` "to keep things simple" → panic in shared state
- Broad error handling ("catch anything, continue") → fail-open instead of fail-closed
- Ignoring concurrency (works for single-threaded happy path)
- Adding a dependency for convenience → dependency sprawl
- Plausible-sounding but wrong `// SAFETY:` comments

The fix: **a spec so precise that these SaaS defaults have nowhere to hide.**

## Interview Pattern: Code Review Red Flag

```
Q: "You're reviewing this Rust function. What's your instant concern?"

Code:
  pub fn lease_path(path: PathId) -> Result<Lease> {
    if !is_available(path) {
        return Err("not available");
    }
    mark_leased(path);  // Two separate operations!
    Ok(Lease { path })
  }

Red flags:
  1. Check-then-act on shared state (is_available, then mark_leased)
     is not atomic. Between those calls, another thread could lease
     the same path.
  
  2. No spec stated what "atomic" means. Is this a bug or intended?
  
  3. No explicit mention of synchronization. Mutex? RwLock? Atomic?

Strong review answer:
  'This has a race condition if called from multiple threads.
  
  is_available(path) returns true
  [context switch to another thread]
  Other thread also sees true, also calls mark_leased(path)
  Both threads think they have the lease
  
  Correct implementation: check-and-set must be atomic. Options:
    1. Hold a Mutex throughout the operation
    2. Use compare-and-swap at the atomic level
    3. Restructure to make them a single operation
  
  But first question: what does the spec say this should do?
  If there's no spec, I ask: what is the actual invariant here,
  and how is it enforced? Until that's clear, I cannot approve.'"
```

## The Spec-First Workflow (Concrete Steps)

```
Step 1: Write the invariant (30 mins)
  Document: what must always be true about the state?
  Example: "A socket is either in IDLE state OR in exactly one
           pending operation's queue, never both."

Step 2: Write the failure modes (30 mins)
  For each thing that can go wrong:
    - What's the safe behavior?
    - What's explicitly not allowed?
  Example: "On allocation failure: return error immediately,
           do NOT partially update state. State must be
           roll-backable to pre-call."

Step 3: Call out concurrency explicitly (15 mins)
  "This entire function must be called under lock L"
  "These two operations can race; they're synchronized by M"
  "This is single-threaded only"

Step 4: Only THEN show it to the agent
  Agent now has constraints that prevent SaaS-shaped instincts

Step 5: Code review focused on invariant, not just syntax
  Does the implementation actually maintain the invariant
  at every step? Trace through edge cases by hand.
```

## AI Lab / Systems Example

```
Spec (from memory):
  "Fine-tuning coordinator must:
   1. Track N checkpoints in a B-tree (sorted by loss)
   2. When model diverges (loss > 2× best), automatically restore
      from best checkpoint
   3. Emit audit log for every restore
   4. Support pausing/resuming mid-epoch
   
   Invariants:
   - Only one restore can be in-flight at a time (hold lock)
   - Audit log is append-only, never rolled back
   - Resume must start from the exact epoch where pause happened
   
   Failure modes:
   - If restore fails: leave state unchanged, return error, let caller
     retry. Do NOT partially restore.
   - If audit log write fails: treat as critical error, stop training."

Agent with this spec:
  - Won't use unwrap() (will see "handle failure" requirement)
  - Won't race on checkpoint access (will see "hold lock")
  - Won't silently skip audit log (will see "critical error")
```

## What To Watch For in Agent-Generated Code

| Red flag | What it means | Fix |
|---|---|---|
| `.unwrap()` / `.expect()` | Panic condition not justified | Ask agent: why is this impossible? If answer is vague, add error handling |
| No `// SAFETY:` on unsafe | No proof the unsafe is safe | Every unsafe block needs a comment naming what invariant holds and why |
| Check-then-act pattern | Likely race condition | Is this guarded by a lock? Is it atomic? State in spec. |
| "Error: ..." string | No structured error type | Specify error enum, each variant means something. |
| Broad error handling | Fail-open default | Spec says explicitly: fail-closed unless exception noted. |

## The Code Review Checklist (Stripped Down)

For agent-generated systems code:

1. Does every `unsafe` block have a `// SAFETY:` comment that names the specific invariant it relies on?
2. Does every `.unwrap()` or panic either prove it's impossible or have an explicit justification?
3. Is every check-then-act on shared state guarded by a lock / atomic / restructured to be atomic?
4. Do error paths match the spec's fail-closed-vs-fail-open rule?
5. Did the agent stay in scope? (check blast radius of any changes)

## Stub Content

- **TLA+ for critical protocols** — when the spec should be formal
- **TOCTOU (time-of-check-to-time-of-use)** — specific race condition pattern
- **Idempotency** — spec requirement for anything retryable
- **Verification beyond tests** — fuzzing, sanitizers, model-checking

The theme: **spec-first makes agent-assisted systems code safe.** The spec is your insurance against SaaS instincts.
