# Error Handling Standards: Status Codes, Messages, Retry Semantics

## Why Standardized Error Handling Matters

Client makes a payment request. Gets HTTP 500.

Questions:
- Can I retry? (Is it transient or permanent?)
- Did the payment go through? (Unsafe to retry without knowing)
- What went wrong? (Help me debug)

Without standards: Client guesses. Pays twice, or loses the payment.

With standards: Client knows exactly what to do.

## HTTP Status Codes: What They Mean

### 2xx Success (Request worked)
- **200 OK:** Request succeeded, body has result
- **201 Created:** Resource created successfully
- **202 Accepted:** Request queued, will process asynchronously
- **204 No Content:** Success, no body (e.g., DELETE succeeded)

### 4xx Client Error (Client's fault, don't retry)
- **400 Bad Request:** Malformed request, fix and resubmit
- **401 Unauthorized:** No auth credentials, authenticate first
- **403 Forbidden:** Authenticated but not permitted
- **404 Not Found:** Resource doesn't exist
- **409 Conflict:** State conflict (e.g., trying to create duplicate)
- **422 Unprocessable Entity:** Request is valid but fails business logic

### 5xx Server Error (Server's fault, may be transient)
- **500 Internal Server Error:** Something broke, might be transient
- **502 Bad Gateway:** Upstream service failed
- **503 Service Unavailable:** Overloaded, try again later
- **504 Gateway Timeout:** Upstream didn't respond in time

## Picking the Right Status Code

### Problem: "Payment validation failed (insufficient funds)"

**Wrong:**
```http
HTTP 500 Internal Server Error
{"error": "validation failed"}
```
❌ Client thinks it's transient → retries → charges multiple times

**Right:**
```http
HTTP 422 Unprocessable Entity
{"error": "insufficient_funds", "amount_needed": 50, "balance": 30}
```
✓ Client knows it won't work until balance increases

### Problem: "Database connection error"

**Wrong:**
```http
HTTP 400 Bad Request
{"error": "database error"}
```
❌ Client thinks it's their fault → doesn't retry

**Right:**
```http
HTTP 503 Service Unavailable
Retry-After: 30

{"error": "service_temporarily_unavailable"}
```
✓ Client knows to retry in 30 seconds

## Error Response Format: Consistency

### Standard Error Object

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Account has insufficient balance",
    "status": 422,
    "details": {
      "available": 30,
      "required": 50,
      "shortfall": 20
    },
    "request_id": "req_abc123",
    "timestamp": "2025-01-15T12:30:45Z"
  }
}
```

**Why each field:**
- **code:** Machine-readable, use for logic (e.g., `if code == 'INSUFFICIENT_FUNDS'`)
- **message:** Human-readable, for logs/UI
- **status:** HTTP status (also in response header, here for convenience)
- **details:** Context to fix it (how much is missing?)
- **request_id:** For debugging, correlate logs
- **timestamp:** When error occurred

## Retry Semantics: When and How

### Idempotent Requests (Safe to Retry)

These requests produce the same result no matter how many times you send them:
- **GET:** Reading data (safest)
- **PUT:** Updating to specific state (idempotent if same body)
- **DELETE:** Deleting (once gone, retrying fails with 404, which is fine)

**Safe to auto-retry on transient errors (5xx, timeout, network).**

### Non-Idempotent Requests (Risky to Retry)

- **POST:** Creating new resource (retry → duplicate)
- **PATCH:** Applying diff (retry → applies multiple times)

**Unsafe to retry unless:**
1. Request has idempotency key
2. Client checks response to confirm success

## Retry Strategy: Exponential Backoff with Jitter

```python
import random
import time

def retry_with_backoff(request, max_retries=5):
    for attempt in range(max_retries):
        try:
            return make_request(request)
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            base_delay = 2 ** attempt
            
            # Jitter: prevent thundering herd
            jitter = random.uniform(0, base_delay * 0.1)
            delay = base_delay + jitter
            
            print(f"Attempt {attempt+1} failed, retrying in {delay:.1f}s")
            time.sleep(delay)
```

**Why exponential backoff?**
- Fast recovery for transient blips (retry after 1s)
- Gradual backoff as issues persist (don't hammer dying server)

**Why jitter?**
- Prevents stampede: if 10K clients all retry at exactly 2s, server gets hammered again

## Interview Pattern: Error Handling at Scale

```
Q: "Your payment API is returning 500 errors for 5% of requests.
   You don't know if the payment went through. How do you fix this?"

Weak answer:
  "Catch exceptions and return a better error message"
  (❌ Doesn't tell client if payment succeeded)

Strong answer:
  "This is an observability problem disguised as an error handling problem.
  
  1. Immediate (next hour):
     - Add unique request_id to every response
     - Log request_id with both request and result
     - If 500 happens, search logs for request_id to see if payment succeeded
     - Return 500 response with request_id
     - Client can call support with request_id to check status
  
  2. Shorter term (this sprint):
     - Implement idempotency keys for all POST requests
     - If payment 500s mid-process, client retries with same key
     - Server recognizes key, returns cached result
     - No double-charge even if request succeeded
  
  3. Longer term (next quarter):
     - Separate write from response: POST returns 202 Accepted
     - Payment processes asynchronously
     - Client polls status endpoint to check result
     - Timeout-safe: even if connection dies, payment either succeeded or failed (no ambiguity)
  
  Why this matters:
    5% of requests = 1000 payments/min (if you're big)
    Each ambiguous payment = support ticket
    1000 tickets/min = you're underwater
    
  The fix isn't better error messages, it's removing ambiguity.
  Request ID + idempotency keys + async processing = clients never need to call support."

Why this signals good judgment:
  - You understood the real problem (ambiguity, not just error messages)
  - You have a staged solution (immediate band-aid + long-term fix)
  - You know idempotency solves payment problems
  - You've thought about scale (1000 tickets/min isn't theoretical)
```

## Checklist: Error Handling in Production

- [ ] Status codes are semantically correct (4xx if client's fault, 5xx if server's)
- [ ] 4xx errors are not retried (client won't fix it)
- [ ] 5xx errors are retried with exponential backoff + jitter
- [ ] Error response includes request_id for debugging
- [ ] POST/PATCH have idempotency keys for safe retries
- [ ] Retry-After header set for 429/5xx
- [ ] Error codes are machine-readable (not just messages)
- [ ] Errors include enough context to fix (not just "error")

## What This Signals

- You've debugged production issues (request_id is essential)
- You understand the difference between retryable and non-retryable errors
- You know idempotency is non-optional for financial systems
- You've thought about client behavior (don't just return errors, help clients succeed)
