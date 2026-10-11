# Auth Flows for Products

## Session-Based vs JWT

```
Session (traditional):
  1. User: POST /login {username, password}
  2. Server: verify password, create session (DB + Redis)
  3. Response: Set-Cookie: session_id=xyz
  4. Browser: stores cookie, sends on every request
  5. Server: lookup session in Redis → verify user
  
  Pros: ✓ Stateful, revoke by deleting session
  Cons: ✗ Server-side state (scales poorly with many sessions)

JWT (token-based):
  1. User: POST /login {username, password}
  2. Server: verify, create JWT: {user_id, exp}.sign(secret)
  3. Response: {token: "eyJ..."}
  4. Client: stores in localStorage, sends in Authorization header
  5. Server: verify signature, extract user_id
  
  Pros: ✓ Stateless, scales (no session lookup)
  Cons: ✗ Can't revoke (token valid until expiry)
  
  Trade-off:
    ├─ Session: small-scale, need fast revocation
    ├─ JWT: large-scale, revocation not critical
```

## OAuth2 / OpenID Connect

```
User wants to: "Log in with Google"

OAuth2 flow (delegated auth):
  1. App: redirect to Google OAuth endpoint
  2. Google: user logs in, grants permission
  3. Google: redirects back to app with code
  4. App server: exchange code for access token (with secret key)
  5. App: uses token to access Google API (get user profile)
  6. App: create session for user
  
  Benefit:
    ├─ User doesn't share password with app
    ├─ App doesn't store passwords
    └─ Google handles auth

OpenID Connect (adds identity):
  ├─ Extends OAuth2 with ID token
  ├─ ID token: contains user claims (name, email, profile)
  └─ Simpler than OAuth2 for login
```

## Multi-Tenant AuthZ

```
Problem: customer_a should only see customer_a's data

JWT approach:
  Token: {user_id, customer_id}.sign(secret)
  
  API: GET /orders
    1. Verify JWT signature
    2. Extract customer_id from token
    3. Query: SELECT * FROM orders WHERE customer_id = {token_customer_id}
    4. Return: only this customer's orders

Database row-level security:
  ├─ Add column: customer_id to every table
  ├─ RLS policy: SELECT * WHERE customer_id = current_user_id
  ├─ Automatic enforcement (even if app bugs out)
  └─ Defense in depth

SSO (Single Sign-On):
  ├─ Centralized auth provider (Okta, Auth0)
  ├─ One login → access to all apps
  ├─ Org admin: add/remove users centrally
  └─ Cost: ~$2-5 per user/month
```

---

## Interview Checklist

- [ ] Session vs JWT tradeoffs
- [ ] OAuth2 for delegated auth
- [ ] OpenID Connect for login
- [ ] Multi-tenant: customer_id in token + DB checks
- [ ] Row-level security: database enforcement
- [ ] SSO: centralized auth for enterprises

## Common Wrong Answers

- ❌ "Store passwords in app" — security risk, don't do it
- ❌ "JWT without signature verification" — forged tokens accepted
- ❌ "No customer_id isolation" — customer_a accesses customer_b data
- ❌ "OAuth2 is harder than session" — usually simpler (offload to provider)
