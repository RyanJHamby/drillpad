# Threat Modeling (STRIDE)

## STRIDE Framework

```
S - Spoofing (identity)
  ├─ Attacker pretends to be someone else
  ├─ Example: fake JWT token
  └─ Mitigation: digital signatures, mTLS

T - Tampering (data integrity)
  ├─ Modify data in transit or at rest
  ├─ Example: change transfer amount in network packet
  └─ Mitigation: HMAC, signatures, encryption

R - Repudiation (denying actions)
  ├─ User denies they did something
  ├─ Example: "I didn't authorize this transfer"
  └─ Mitigation: audit logs, digital signatures

I - Information disclosure (confidentiality)
  ├─ Leak data to unauthorized party
  ├─ Example: sniff unencrypted password
  └─ Mitigation: TLS, encryption, access control

D - Denial of service (availability)
  ├─ Make service unavailable
  ├─ Example: DDoS attack
  └─ Mitigation: rate limiting, CDN, redundancy

E - Elevation of privilege (authorization)
  ├─ Gain higher privileges than allowed
  ├─ Example: regular user becomes admin
  └─ Mitigation: RBAC, principle of least privilege
```

## Data Flow Diagram (DFD)

```
User → Web App → Database
 |       |         |
Identify threat per edge:

User → Web App (spoofing: fake user identity?)
  ├─ Mitigation: authentication

Web App → Database (tampering: modify query?)
  ├─ Mitigation: parameterized queries

Database → Web App (disclosure: leak data?)
  ├─ Mitigation: encryption at rest
```

## Example: E-Commerce

```
Threat: attacker changes order price before checkout

Data flow:
  1. User adds item to cart
  2. Web app stores item + price in session
  3. Checkout: reads session, calculates total
  4. Submit payment with total

Attack vector:
  ├─ Attacker intercepts session
  ├─ Modifies price: $100 → $10
  ├─ Checkout calculates $10
  ├─ Payment processor charges $10 (loss!)

Mitigation:
  ├─ Re-fetch prices from DB (don't trust client session)
  ├─ Sign session data (attacker can't modify without key)
  └─ Validate: server checks total is correct
```

---

## Interview Checklist

- [ ] STRIDE: 6 threat categories
- [ ] Data flow diagram: identify trust boundaries
- [ ] Per-edge threats: spoofing, tampering, disclosure, etc.
- [ ] Mitigations: auth, encryption, signing
- [ ] Test: can attacker modify data in transit?

## Common Wrong Answers

- ❌ "No threat modeling" — find vulnerabilities post-launch (expensive)
- ❌ "Ignore data flow" — miss tampering opportunities
- ❌ "Only focus on authentication" — authorization, data tampering also critical
