# Unsafe Rust Review: Agent-Generated Code in Systems Context

## Why This Specific Lesson

Your systems-rust guide has a full code-review checklist for agent-generated unsafe code. This is a **systems-specific, not general** skill: how to review code an agent wrote when that code touches memory safety, FFI, or the isolation boundary.

The failure mode is: agent generates code that compiles, has a plausible-sounding `// SAFETY:` comment, and is subtly wrong in a way that costs real money or crashes a tenant.

## The Biggest Difference from Code Review of Human-Written Code

Humans usually know why something is unsafe and can explain it (sometimes poorly). **Agents don't have intuition.** They generate plausible-sounding explanations that might not establish the actual invariant.

```
Human unsafe code:
  // We know this is safe because we hand-verified X
  unsafe { ... }
  
Agent unsafe code:
  // SAFETY: This is safe because reasons
  unsafe { ... }
  
The agent wrote the comment confidently. That doesn't mean it's true.
```

## Red Flag: Confident But Wrong Safety Comments

```
Code:
  pub fn get_data(ptr: *const u8, len: usize) -> &'static [u8] {
    // SAFETY: ptr is valid and properly aligned
    unsafe { std::slice::from_raw_parts(ptr, len) }
  }

What's wrong:
  - Assumes &'static lifetime (data lives forever)
  - But maybe the data is on the stack or in a borrowed buffer
  - Agent saw "SAFETY comment exists" and stopped thinking
  
This is dangerous because:
  - Compiles
  - Looks safe (there's a comment!)
  - Will panic or segfault at runtime when the data is freed

The agent's confidence doesn't prove correctness.
```

## The Three-Question Checklist for Agent-Generated Unsafe

### Question 1: Does the `// SAFETY:` Comment Name the Actual Invariant?

```
Weak comment:
  // SAFETY: This is safe because we checked earlier
  unsafe { ... }

Questions your review should ask:
  - Which check? Where?
  - How do we *know* it still holds now?
  - What could invalidate it?

Strong comment:
  // SAFETY: ptr came from vec.as_ptr() and vec is live for the scope.
  // len was checked < vec.len() above. No thread can mutate vec
  // because we hold &mut self. Safe for this scope only.
  unsafe { ... }

This comment is specific enough that you can verify it by reading nearby code.
```

### Question 2: Is the Unsafe Actually Necessary, or Could Safe Code Do It?

```
Code:
  unsafe { *ptr = value; }
  
Questions:
  - Could this use a Cell<T> or Mutex<T> instead?
  - Is the unsafe only here because the agent didn't know the safe alternative?
  - If you replaced it with safe code, what would break?

If the answer is "nothing would break," the unsafe is unnecessary.
Agent generated something that compiles; it's not always the best solution.
```

### Question 3: Would This Invariant Still Hold After Refactoring?

```
Code:
  pub fn process(data: &mut [u8]) {
    unsafe {
      // SAFETY: buffer is valid because we take &mut self
      libc::memcpy(buf as *mut _, data.as_ptr(), len)
    }
  }

Future change someone might make:
  - Refactor to process in smaller chunks
  - Pass data to another function
  - Change the lifetime of data
  
The comment says "valid because we take &mut self" but doesn't explain
*why* that guarantees the pointer is still valid after being used in
memcpy.

A more durable comment:
  // SAFETY: buf and data must have non-overlapping lifetimes and
  // sufficient size. We guarantee this by:
  //   1. buf is from self.buffer (self's ownership)
  //   2. data is a borrowed reference (can't outlive)
  //   3. len was checked to be <= min(buf.len(), data.len())
  // These guarantees survive refactoring as long as the check happens here.
```

## FFI-Specific Red Flags (Agent Generated)

```
Weak:
  unsafe { some_c_function(ptr) }
  // SAFETY: ptr is valid
  
What's missing:
  - What are the C function's actual expectations?
  - Is this calling convention correct?
  - Are there hidden side effects or state mutations?
  - Does the C function validate input or assume it?

Better review:
  - Read the C function signature (from a header or man page)
  - Verify each argument matches the expected type, alignment, lifetime
  - Check if there's undefined behavior if inputs are malformed
  - Test with intentionally bad inputs (if it crashes, agent guessed wrong)
```

## Interview Pattern: Agent-Generated Unsafe Code Review

```
Q: "An agent generated this function. What's wrong with it?"

Code:
  pub fn write_to_buffer(buf: *mut u8, data: &[u8]) {
    // SAFETY: buffer is valid
    unsafe {
      std::ptr::copy_nonoverlap(data.as_ptr(), buf, data.len());
    }
  }

Weak answer:
  "It compiles, looks safe to me"
  (❌ Doesn't engage with the safety claim)

Strong answer:
  "The comment 'buffer is valid' doesn't actually establish safety.
  
  Real invariants this needs:
  1. buf must be non-null and properly aligned for u8
  2. buf must point to at least data.len() bytes of writable memory
  3. buf and data.as_ptr() must not overlap
  4. buf must remain valid for the entire copy (no concurrent frees)
  
  The comment establishes none of these. Better approach:
  
  Option A: Safe version
    pub fn write_to_buffer(buf: &mut [u8], data: &[u8]) {
      buf[..data.len()].copy_from_slice(data);
    }
  
  This is safer, clearer, and doesn't need unsafe. Ask the agent:
  why can't we use &mut [u8] instead of *mut u8? If the answer is
  'I don't know,' the agent is guessing.
  
  Option B: If raw pointers are actually necessary:
  
  // SAFETY: 
  // - buf must be non-null and point to at least data.len() bytes
  // - buf must be writable for its lifetime
  // - Caller guarantees buf and data don't overlap (checked at call site)
  // Invariants enforced by:
  //   [list the actual checks that exist in the codebase]
  // If caller violates these, the behavior is undefined.
  unsafe { ... }
  
  This comment is reviewable — either the checks exist or they don't."

Why this signals good judgment:
  - You didn't trust the agent's confidence
  - You identified what safety actually requires
  - You considered whether safe alternatives exist
  - You can distinguish "code that compiles" from "code that's safe"
```

## Unsafe Code Red Flags (Automated Check)

When you see an agent-generated unsafe block:

- [ ] Is there a `// SAFETY:` comment?
- [ ] Does the comment name specific invariants (not vague reassurances)?
- [ ] Can you verify each invariant by reading nearby code?
- [ ] Would this invariant survive a refactor?
- [ ] Could safe Rust do the same thing?
- [ ] Is there any `unwrap()`, `expect()`, or `as` cast (transmute)?

If any answer is "no" or "unclear," the unsafe needs revision.

## What This Signals

- You've reviewed systems code at the boundary between safe and unsafe
- You understand that agent code needs the same rigor as human code, often more
- You can distinguish "the agent wrote something" from "the agent solved it correctly"
- You're a risk manager, not just a code reader

In Rust systems roles (Firecracker-adjacent, embedded systems, high-reliability), this is a core responsibility: making sure unsafe code is justified and correct, not just plausible.
