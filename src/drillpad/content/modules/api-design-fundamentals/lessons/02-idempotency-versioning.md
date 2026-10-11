# Idempotency Keys & API Versioning: Handling Retries & Evolution

## Why Idempotency Matters in Production

Problem: A payment request times out. The client can't tell if it succeeded.
- Did the payment go through?
- If I retry, do I charge twice?

Without idempotency: You have to call support ("Did you charge me?"). Business loses trust.

With idempotency: Client can safely retry. Same request = same result, always.

## Idempotency Keys: The Mechanism

### How It Works

```
Client generates unique ID for request:
  Request 1: POST /payments with Idempotency-Key: abc123
             → Creates payment, returns ID
  
  Network fails during response
  
  Request 2: POST /payments with Idempotency-Key: abc123
             → Server recognizes key, returns cached result
             → No double-charge
```

### Implementation Pattern

```python
# Server side
@app.post("/payments")
def create_payment(data, idempotency_key):
    # Check if we've seen this key before
    if key_exists(idempotency_key):
        return get_cached_result(idempotency_key)
    
    # First time: execute
    result = process_payment(data)
    
    # Cache for future retries
    cache_result(idempotency_key, result)
    
    return result
```

**Key requirements:**
- Key must be **unique per operation** (not per user)
- Key must **survive retries** (stored, not in-memory)
- Key must **expire** (after 24h, not forever—space is finite)
- Key must **be scoped** (payment key ≠ refund key)

## When Idempotency Is Critical

**Tier 1: Always idempotent**
- Payments, transfers, financial transactions
- Account creation, deletions
- Resource state changes that can't be undone

**Tier 2: Nice to have**
- Order placement
- Appointment booking
- Any user-facing creation

**Tier 3: Not necessary**
- Read-only operations (GET is idempotent by definition)
- Analytics events (dups are acceptable)
- Logging

## API Versioning: Handling Evolution

### Why Versions Exist

Early API: `/users/{id}` returns `{name, email}`

6 months later: Product wants phone numbers too.

You can't just add `phone` to the response—old clients don't expect it, might break.

Solution: Versions let you support old clients while rolling out new features.

### Versioning Strategies

**Strategy 1: URL versioning (most explicit)**
```
GET /v1/users/{id}     → {name, email}
GET /v2/users/{id}     → {name, email, phone}
```
Pros: Clear, easy to route
Cons: Multiple codebases, more maintenance

**Strategy 2: Header versioning (most flexible)**
```
GET /users/{id}
  Accept: application/vnd.company.v2+json
  → {name, email, phone}
```
Pros: Single codebase, granular
Cons: Hidden in headers, harder to test

**Strategy 3: Query parameter (middle ground)**
```
GET /users/{id}?api_version=2
  → {name, email, phone}
```
Pros: Visible, testable
Cons: Pollutes query space

### Deprecation Path (Critical)

You can't support all versions forever. Plan the deprecation:

```
Today (Jan 2025): Launch v2 alongside v1
6 months (Jul 2025): Announce v1 sunset in Dec
Dec 2025: v1 disabled
```

**Rules:**
- Announce 6 months before sunset
- Provide migration guide
- Log warnings in v1 responses: `Sunset-At: 2025-12-31`
- Track who's still using old version (monitor adoption)

## Interview Pattern: Versioning Trade-offs

```
Q: "Your API has 100,000 mobile clients on v1. You need to add
    phone numbers to the user endpoint. How do you handle this?"

Weak answer:
  "Just add phone to the response"
  (❌ Breaks old clients that don't expect it)

Strong answer:
  "I'd use header versioning or query params, so I can support both:
  
  1. Immediate: Old clients (v1) get {name, email}
                 New clients (v2) get {name, email, phone}
  
  2. Monitoring: Track v1 adoption. If <5% of traffic in 3 months,
                 deprecate faster. If >20%, extend timeline.
  
  3. Sunset: 6-month notice with clear dates + migration guide.
  
  Why header over URL? Avoids maintaining two /v1 and /v2 code paths.
  Why not just add phone? Old clients don't expect new fields, 
  might parse incorrectly or assume schema is stable.
  
  Cost: ~2h to implement version routing + monitoring.
  Benefit: Zero downtime for old clients, smooth transition."

Why this signals good judgment:
  - You understood backward compatibility (not everyone does)
  - You have a migration timeline (not "someday")
  - You monitored adoption (data-driven deprecation)
  - You chose explicit versioning strategy (not implicit breaking changes)
```

## Common Pitfalls

| Pitfall | Cost | How to avoid |
|---|---|---|
| **No idempotency on payments** | Duplicate charges, support load | Implement key + cache before launch |
| **Idempotency key expires too fast** | Client retries after expiry → duplicate | 24h+ expiry for payments |
| **Breaking change without versioning** | Old clients crash | Versions mandatory for production APIs |
| **Deprecate too fast** | Angry customers still on v1 | 6-month notice minimum |
| **Support every old version forever** | Code bloat, hard to add features | Set sunset date, enforce migration |

## What This Signals

- You understand why production APIs need safeguards (retries fail, clients crash)
- You've thought about long-term API stability (not just launch day)
- You can balance old clients with new features (versioning trade-offs)
- You see idempotency and versioning as *structural*, not optional
