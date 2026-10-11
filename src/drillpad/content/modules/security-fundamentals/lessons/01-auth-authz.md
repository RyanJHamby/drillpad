# Authentication vs Authorization

## Definitions (Often Confused)

```
Authentication: "Who are you?"
  Prove your identity (username/password, OAuth token, certificate)
  
Authorization: "What can you do?"
  What resources you can access
  
Example: Login to Gmail
  Authentication: email + password proves you're you
  Authorization: you can read your emails, not others' emails
```

## Authentication Patterns

```
1. Session-based (stateful)
  Client: POST /login {user, pass}
  Server: Create session, set cookie
  Client: Browser auto-sends cookie
  Pro: Simple, browser-native
  Con: Server must store sessions
  
2. Token-based (stateless)
  Client: POST /login {user, pass}
  Server: Return JWT token
  Client: Send in Authorization header
  Pro: Stateless, scalable
  Con: Tokens can't be revoked quickly
  
3. OAuth (delegated)
  Client: "Login with Google"
  Google: Verifies identity, returns token
  Pro: Password never shared, social login
  Con: Dependency on OAuth provider
```

## Authorization Patterns

```
1. Role-based (RBAC)
  User has role (admin, user, guest)
  Role has permissions (create, read, delete)
  
2. Attribute-based (ABAC)
  User attributes (dept=eng, level=senior)
  Resource attributes (owner=user, sensitivity=public)
  Policy: if user.dept == resource.owner then allow
  
3. Resource-based
  Each resource defines who can access
  Example: User A grants User B read-only access
```

## System Design: Auth/Authz Placement

```
Single server:
  /api/orders (auth+authz in handler)
  
Distributed:
  API Gateway → checks auth (JWT valid?)
  Service → checks authz (can user access this order?)
  
Example:
  API Gateway: "Is token valid?" (all requests)
  Order Service: "Can user access order 123?" (specific to service)
```

## Interview Pattern

```
Q: "Design authentication for marketplace with vendors"

Answer:
  "Multi-tenant auth:
  
  Authentication: OAuth (Google, Facebook)
   - Secure, user-familiar, social login
   
  Authorization: RBAC + resource-based
   - Vendor role: can create/edit their own products
   - Buyer role: can read products, not edit
   - Admin role: can manage all
   
  Implementation:
   - JWT token from auth service
   - API gateway validates JWT
   - Order service checks role (vendor can edit?)
   - Product service checks ownership (my products?)
   
  Token revocation:
   - If user password changes, invalidate sessions
   - For OAuth tokens, rely on provider
   
  Security:
   - HTTPS only (token in header)
   - No sensitive data in JWT
   - Short-lived tokens (1 hour expiry)"
```

