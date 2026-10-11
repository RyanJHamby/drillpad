# Scoring Yourself: What Separates 70 from 85 from 90

## The 70 (Good Enough / Hire)

```
✓ Correct architecture (works for scale)
✓ Identifies main bottleneck
✓ Explains basic tradeoff
✓ Handles follow-ups (mostly)
✗ Missing: deep reasoning on why this specific tradeoff
✗ Missing: alternative approaches considered
✗ Missing: measurement/metrics

Example:
  Q: Design cache
  A: "Use Redis with LRU eviction. Hit rate ~95%"
  
  Score: 70 - correct, but shallow
  Why: No reasoning about WHY LRU vs LFU
```

## The 85 (Strong Hire / Preferred)

```
✓ Correct architecture
✓ Identifies bottleneck
✓ Explains tradeoff deeply (cost-benefit)
✓ Considers alternatives ("I looked at X, picked Y because...")
✓ Adapts design to constraint changes
✓ Mentions metrics (how to verify)
✗ Missing: some edge case or production detail

Example:
  Q: Design cache
  A: "Use Redis with LRU eviction.
      Tradeoff: LRU is simple vs LFU is smarter for skewed workloads.
      For YouTube (Zipfian distribution), LFU better.
      Cost: LFU has ~5% overhead.
      Metric: Monitor hit rate, alert if < 90%"
  
  Score: 85 - strong reasoning, adaptable
  Why: Shows understanding of when each pattern applies
```

## The 90+ (Exceptional / Must Hire)

```
✓ Everything at 85
✓ Proactively identifies non-obvious issues
  ("Cache stampede: when item expires, 100 requests hit DB")
✓ Proposes solution ("Use probabilistic expiry")
✓ Shows production thinking
  ("In production, we measure P99, not average hit rate")
✓ Questions that reveal deep understanding
  ("How often do we expect X failure mode?")

Example:
  Q: Design cache
  A: "Redis with LRU...
      But there's a cache stampede risk: when item expires,
      all requests miss simultaneously, hammer origin.
      Solution: probabilistic expiry or refresh-on-miss.
      
      Also: need to think about:
      - Memory pressure (when heap fills, what happens?)
      - Partial failures (if Redis node fails, cascade to origin?)
      - Network serialization (is Redis protobuf-compatible?)
      
      I'd monitor: hit rate, eviction rate, staleness distribution"
  
  Score: 90 - anticipates problems, thinks holistically
```

## Red Flags That Drop You (to 50-60)

```
❌ Correct architecture but can't explain WHY
   "Use Redis"
   "Why not Memcached?"
   "Uh... Redis is better?"
   
❌ Misses obvious bottleneck
   Design doesn't scale to stated requirements
   
❌ Defends wrong tradeoff
   "Consistency is always better"
   "No, not for this constraint"
   
❌ Can't adapt when constraints change
   Interviewer: "Now needs to be cheaper"
   You: "My design still works"
   (It does, but you didn't optimize for new constraint)
   
❌ No metrics / can't measure success
   "How would you know if this works?"
   "Uh... it would be fast?"
```

## Green Flags That Push You to 85+

```
✅ Explicit tradeoff reasoning
   "I'm trading consistency for latency because..."
   
✅ Numbers
   "Cache hit rate would be ~95% based on..."
   
✅ Production thinking
   "In production, we'd also need..."
   
✅ Adaptation
   Interviewer changes constraints
   You: "That changes things. Here's the new approach..."
   
✅ Questions
   You ask interviewer good questions
   (Shows you're thinking, not just monologuing)
```

## Self-Scoring in Interview

```
After your design, score yourself:

Did I:
  [ ] Explain the bottleneck clearly?
  [ ] Reason about tradeoff (cost vs benefit)?
  [ ] Consider alternatives?
  [ ] Propose metrics?
  [ ] Adapt when constraints changed?
  [ ] Anticipate failure modes?

Score:
  0-2 yes: 70 (needs improvement)
  3-4 yes: 80 (solid)
  5-6 yes: 85+ (strong)
```

