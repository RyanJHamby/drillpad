# Payments Integration for Builders

## Stripe API Basics

```
Charge flow:

1. Frontend: customer enters card details
   └─ Use Stripe.js (secure, PCI compliant)
   └─ Never send raw card to your server (PCI violation)

2. Stripe creates PaymentIntent (server-side)
   └─ POST /payment_intents {amount, currency}
   └─ Returns client_secret

3. Frontend: confirm payment with client_secret
   └─ Stripe.confirmCardPayment(clientSecret, {card})
   └─ Stripe processes, returns result

4. Webhook: Stripe notifies you (payment.succeeded)
   └─ Fulfill order (ship product, enable account)
   └─ Webhook signature verification (secret signing key)

Cost:
  ├─ 2.9% + $0.30 per transaction
  ├─ $10 revenue = $0.59 fee
  └─ Competitive (vs PayPal, Square)
```

## Webhooks & Idempotency

```
Problem: Stripe sends payment.succeeded webhook
  ├─ Your server: fulfill order
  ├─ Network dies before response
  ├─ Stripe: didn't hear ACK, retries webhook
  ├─ Your server: processes again (duplicate fulfillment!)

Solution: idempotency

  Request header: Idempotency-Key: uuid-123
  
  Server:
    1. Check: have I processed uuid-123 before?
    2. If yes: return cached response
    3. If no: process, cache result with uuid-123
  
  Result:
    ├─ First webhook: processes order
    ├─ Retry webhook (same uuid): returns cached result
    └─ No duplicate fulfillment
```

## Reconciliation

```
Your system of record:
  ├─ orders table: order_id, amount, status, stripe_payment_id
  ├─ Status: pending → paid → fulfilled

Nightly reconciliation:
  1. Query Stripe: all charges from past 24h
  2. Compare with your orders table
  3. Find mismatches:
     ├─ Charge in Stripe but not in orders (missed webhook?)
     ├─ Order in DB but charge failed in Stripe
  4. Investigate and fix
  
Webhook failures:
  ├─ Stripe retries for 3 days
  ├─ If still failing: manual follow-up required
  └─ Reconciliation catches these

Cost impact:
  ├─ One failed webhook = lost revenue
  ├─ Reconciliation finds and fixes
  └─ Worth the engineering effort (100% revenue recovery)
```

---

## Interview Checklist

- [ ] PCI compliance: never touch raw cards (use Stripe.js)
- [ ] Webhooks: idempotent processing with signature verification
- [ ] Reconciliation: nightly comparison with Stripe API
- [ ] Idempotency keys: prevent duplicate charges on webhook retry
- [ ] Cost: 2.9% + $0.30

## Common Wrong Answers

- ❌ "Store card numbers in database" — PCI violation, illegal
- ❌ "No idempotency" — duplicate charges on webhook retry
- ❌ "No reconciliation" — missing charges not detected
