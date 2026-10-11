# Payments: Payment Adapter (Exactly-Once, Idempotency, Reconciliation)

## Firm Archetype: AWS, Stripe, Block, PayPal

**Problem:** Process payments safely:
- No double-charges
- No lost transactions
- Handle retries, failures, crashes gracefully
- Reconcile divergences

**Why hard:** Money is at stake. Small bugs = customer fury + regulatory issues.

---

## Core Design: Idempotency + Async

```
Synchronous (bad):
  Request: POST /charge?amount=100
  Server: charge payment, return response
  Problem: if response lost, client retries, double charge
  
Asynchronous (good):
  Request: POST /charge?amount=100&idempotency_key=abc123
  Server: return 202 (accepted), process async
  Callback: POST client_webhook?result=success
  Problem: harder to reason about, but safer
```

---

## Implementation: SQS FIFO + DynamoDB

```python
# Step 1: API receives request
@app.post("/charge")
def charge_payment(seller_id, amount, idempotency_key):
    """
    Accept charge, store in SQS, return immediately.
    """
    
    # Check idempotency store (fast)
    previous = idempotency_table.get(idempotency_key)
    if previous:
        return {"status": previous["status"], "charge_id": previous["charge_id"]}
    
    # Mark as pending
    idempotency_table.put(
        idempotency_key,
        {"status": "pending", "seller_id": seller_id, "amount": amount}
    )
    
    # Queue for processing (SQS FIFO)
    sqs.send_message(
        QueueUrl='https://sqs.../payment.fifo',
        MessageBody=json.dumps({"seller_id": seller_id, "amount": amount}),
        MessageDeduplicationId=idempotency_key,
        MessageGroupId=f"seller-{seller_id}"  # FIFO within seller
    )
    
    return {"status": "pending"}

# Step 2: Background worker processes
def process_payment_queue():
    while True:
        message = sqs.receive_message()
        if not message:
            continue
        
        payload = json.loads(message['Body'])
        idempotency_key = message['MessageDeduplicationId']
        
        # Charge
        try:
            charge_id = payment_provider.charge(payload['seller_id'], payload['amount'])
            result = {"status": "success", "charge_id": charge_id}
        except Exception as e:
            result = {"status": "failed", "error": str(e)}
        
        # Store result + mark processed
        idempotency_table.update(
            idempotency_key,
            {"status": result["status"], "charge_id": result.get("charge_id")}
        )
        
        # Webhook callback to client
        notify_seller(payload['seller_id'], result)
        
        # Acknowledge message
        sqs.delete_message(message['ReceiptHandle'])

# Step 3: Reconciliation job (daily)
def reconcile_payments():
    """
    Find discrepancies between our records and payment provider.
    """
    our_charges = idempotency_table.query_all(status="success")
    provider_charges = payment_provider.list_charges(since=yesterday)
    
    # Find missing charges
    our_ids = set(c['charge_id'] for c in our_charges)
    provider_ids = set(c['id'] for c in provider_charges)
    
    missing_in_provider = our_ids - provider_ids  # We say charged but provider doesn't
    missing_in_ours = provider_ids - our_ids      # Provider says charged but we don't
    
    for charge_id in missing_in_provider:
        log_alert(f"MISSING_IN_PROVIDER: {charge_id}, investigate")
    
    for charge_id in missing_in_ours:
        log_alert(f"MISSING_IN_OURS: {charge_id}, investigate")
```

---

## Real Example (Your Resume Claim)

"Payment Adapter Service (parallel third-party verification, circuit breakers, idempotent retries, async callbacks), cutting Japanese seller onboarding from 6 days to 5 minutes"

**Problem:** Sellers had to wait days for payment confirmation.

**Root cause:** Synchronous payment flow (request → charge → response). If payment provider slow, everything queues.

**Solution:**
- Async: return 202 (accepted) immediately
- SQS FIFO: queue payments in order
- Idempotency: retry-safe via idempotency key
- Circuit breaker: if payment provider down, fail fast (don't queue forever)
- Parallel verification: check other payment methods in parallel

**Result:** Seller sees "Payment accepted" in 5 minutes (vs 6 days waiting for confirmation).

---

## Design Decisions

**Why SQS FIFO instead of random order?**
- FIFO: guarantees order (important for audit trail)
- Fairness: requests processed in order, not starved by retries

**Why idempotency key instead of just retry?**
- Idempotency: safe to retry 100x, only charges once
- Without: risky to retry (might double-charge)

**Why circuit breaker?**
- If payment provider down, don't wait forever
- Fail fast, queue for retry later
- Protects from cascading failure

**Why reconciliation job?**
- Find drift between our DB and payment provider
- Detect bugs, fraud, corruption
- Alert team immediately

---

## Q&A

**Recall 1:** Why async better than sync for payments?**

*Must-say:*
- Async: decouple client from payment provider latency
- Client gets response immediately, doesn't wait for charge
- Payment completes in background

**Probe 1:** Idempotency key is abc123. Client retries 10 times. Charge happens once. Why?

*Expected:*
- First request: idempotency_key not in table, charge, store result
- Retries 2-10: idempotency_key exists, return cached result
- DynamoDB conditional put prevents race conditions

**Numeric 1:** Payment provider has 1% failure rate. 10K payments/day. How many failures?

*Working:*
- 10K * 1% = 100 failures/day
- With circuit breaker: after 10 failures in row, stop trying for 1 min
- Retry later when provider recovers
- All retries are idempotent (safe)

---

## Questions for the Interviewer

- How do you handle payment provider outages?
- How often do you reconcile? (hourly, daily?)
- Have you had a double-charge bug? (what caused it?)
- What's your P99.9 latency? (just for confirmation, not critical path)
