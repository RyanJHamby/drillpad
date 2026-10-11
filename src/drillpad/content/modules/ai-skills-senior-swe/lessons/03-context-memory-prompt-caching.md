# Context, Memory, and Prompt Caching: Making AI Systems Fast and Cheap

## The Core Principle

**Everything the model needs to know for this call must be in the context window, or it doesn't exist.** This sounds obvious but is violated constantly in practice. "The agent should know our API returns errors this way" is not true unless that fact is actually present in the current context.

This is the single highest-leverage skill for making AI systems feel fast, cheap, and reliable.

## The Three Mechanisms

```
1. Context editing / pruning
   Remove stale tool results, summarized thinking blocks
   Keeps transcript lean mechanically
   Manages a SINGLE SESSION's context budget
   
2. Compaction / summarization
   Compress earlier turns into a condensed block
   When approaching context limit
   Lossy but preserves gist
   Manages a SINGLE SESSION's context budget
   
3. Memory (persistent storage outside context)
   Files, databases, memory stores
   Survives across sessions
   Cross-SESSION persistence
```

**Rule of thumb:** editing and compaction manage a *single session's* context budget; memory is for *cross-session* persistence. A serious long-running agent uses all three.

## Interview Pattern: The Slow Agent

```
Q: "Our agent feels slow. Each task takes 30 seconds. Why?"

Common wrong answer:
  "The model is too slow, use a faster one"
  
Better diagnostic:
  "Slow is almost always a context problem, not a model problem.
  The model is re-deriving things it should already know."
  
Three questions:
  
  1. Is the agent re-explaining your project architecture every session?
     → Write a project-instruction file (CLAUDE.md, AGENTS.md)
     → Saves ~5K context tokens per session, 5+ seconds per round
  
  2. Are you feeding it your entire codebase history every time?
     → Trim to relevant files, use file search, not whole-repo dumps
     → Saves 20K+ context tokens
  
  3. Is the agent looping 10 times when it should loop 2?
     → That's a task-tier or spec problem (it's re-deriving because
       the spec is ambiguous)
     → Fix the spec, not the model
  
  Example fix order:
    - Write CLAUDE.md with your architecture (saves 30%)
    - Add an eval (catches when spec is ambiguous) (saves 40%)
    - Only then consider a faster model (saves 10%)"
```

## The Three Context Artifacts Worth Knowing Cold

### 1. Project-Instructions File (Highest ROI)

```
What it is:
  CLAUDE.md or AGENTS.md, checked into the repo
  Architecture summary, conventions, how to run tests
  
Why it matters:
  Agent re-derives your project's shape every session without it
  With it: agent starts warm, knows what not to touch
  
Example:
  # Project: OrderBook Engine
  
  ## Architecture
  - Lock-free MPSC queue for order ingestion
  - HashMap for order tracking (indexed by order_id)
  - Matching engine processes periodically, not on every order
  
  ## Conventions
  - All latency-critical code is in latency/ crate
  - All tests run: cargo test; must pass before merging
  - Never touch unsafe/ without thread-safety proof
  
  ## How to run
  - cargo build --release
  - cargo test -- --test-threads=1 (required for timing tests)
  
  ## Don't touch
  - The memory allocator (we use jemalloc, changing it breaks benchmarks)
  - Cross-thread integer overflow checks (we use wrapping_ for a reason)
  
Return value: first-session speed goes from 15 seconds to 3 seconds
```

### 2. Memory Files (For Cross-Session Learning)

```
What it is:
  /memories directory or equivalent
  One file per lesson learned
  Updated, not duplicated; deleted when wrong
  
Why it matters:
  "Agent keeps re-discovering the same architecture facts"
  
Example structure:
  /memories/orderbook-bottleneck.md
  ---
  The bottleneck is std::map rebalancing, not lock contention.
  Profiling showed 40% of CPU in node insertion (red-black tree ops).
  The fix: switch to pre-allocated arena + manual linked list.
  This stays until it's no longer true (next refactor, delete it).
  
  /memories/test-flakiness.md
  ---
  The timing test at tests/latency/p99.rs is flaky under load.
  Root cause: system GC not isolated. Don't chase it.
  The real metric is in results/latest.json from `pow run`.
```

### 3. Prompt Caching (The Free Win)

**Prompt caching** is server-side caching of a stable prompt prefix.

```
How it works:
  Big system prompt (15KB): "You are an expert in X language, here are conventions..."
  Project context (20KB): your CLAUDE.md + relevant design docs
  
  First call: 35KB read fresh
  Second call with same prefix: 35KB cached, costs ~10% vs. fresh
  
Real economics:
  Without caching: every call pays 35KB overhead
  With caching: first call pays it, next 100 calls are cheap
  
Order of magnitude: 50-90% cost reduction on agentic loops.
```

The catch:
- Caching is prefix-match: *any change anywhere earlier invalidates it*
- Don't put `datetime.now()` in your system prompt (kills cache hit rate)
- Don't regenerate your tool list non-deterministically
- Verify caching is working via the `cache_read_tokens` field in API response

## Systems Interview: Latency Budget

```
Q: "Your inference latency budget is 2 seconds per request.
   How do you manage context?"

Strong answer:
  "At 2-second budget, context matters because:
  
  Processing 35KB context (unprompted):
    - Network roundtrip: 100ms (client → API → model)
    - Model processing: 500ms (tokenizing, attention)
    - Generate answer: 500ms
    - Total: ~1.1 seconds (without context, just generation)
  
  With context compression:
    - If caching works: cached context reads are 10x cheaper
    - Prefix cache costs ~50ms instead of 500ms
    - Total: ~650ms (saving 450ms per call)
  
  Practical moves:
    1. Write a project-instructions file (drops redundant context)
    2. Use file search instead of dumping whole codebase
    3. Enable prompt caching (API-level optimization)
    4. Trim tool definitions to only what's needed
  
  With all three: each call might go from 1100ms to 400ms.
  That's the difference between 'feels slow' and 'acceptable.'"
```

## AI Lab: Long-Horizon Agent Context

```
Q: "You're building an agent that fine-tunes models over days.
   How do you preserve learning across sessions?"

Answer:
  "Three-layer context strategy:
  
  Layer 1: Session-level (just this fine-tuning run)
    - Last 10 training checkpoints kept in context
    - Current loss curves, recent convergence issues
    - Expires at end-of-session
  
  Layer 2: Cross-session memory (persistent)
    - 'Lessons learned' file:
      Last 5 experiments that failed, why
      Hyperparameter ranges that work for this domain
      Known failure modes (divergence at LR > 0.001, etc.)
  
  Layer 3: Cached stable context (prompt caching)
    - Model architecture (never changes mid-experiment)
    - Dataset characteristics
    - Known good hyperparameter starting points
    - Costs nothing extra once cached
  
  Flow:
    Session 1: Human does experiment, writes down what worked
    Session 2: Agent reads memory file, uses cached architecture,
      has 20KB of expensive context for free, suggests experiments
    Session 3: Agent now has 2 sessions of history to reference,
      suggests 'we've tried higher LR, try lower', leverages learning"
```

## The Real Skill: Curating What Goes In

More context isn't free. It:
- Costs latency (model has to process more tokens)
- Costs money (input tokens)
- Can hurt quality (model has to find signal in noise)

The skill is deciding:
```
Definitely in context:
  - Current task specification
  - Project conventions
  - Previous results the model needs to reference
  - Tool definitions (the model needs these to work)

Probably in context:
  - File headers and docstrings for functions the model touches
  - Relevant architecture patterns
  - Example of similar code it should mimic
  
Probably NOT in context:
  - Entire git history
  - Every test in the codebase
  - API documentation for services not relevant to this task
  - Commented-out old code
```

## What This Signals in Interviews

When you understand context management, you're signaling:
- You've shipped enough to know what makes agents fast
- You understand the economics (latency vs. cost vs. quality)
- You measure before optimizing (you'd benchmark context size)
- You have production intuition (context is a design decision, not an afterthought)

In systems/infra roles, this is a real differentiator. It's the difference between someone who can use Claude Code, and someone who can *direct* an agent effectively at scale.
