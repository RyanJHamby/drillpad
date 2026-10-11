# gRPC & Protocol Buffers: Wire Format, Schema Evolution, Performance

## The Problem

Your backend has 100 microservices. You change the `User` message from `email: string` to `email: optional string`. Some services update; others don't. Requests between old and new services fail silently or crash.

```
Old service sends:
  {id: 123, email: "user@example.com"}

New service receives and expects:
  {id: 123, email: "user@example.com", created_at: timestamp}

If created_at is missing:
  new_service crashes (unmarshalling fails)
  
OR:

Old service is updated, new schema field added:
  {id: 123, email: "user@example.com", phone: "555-1234"}

Old receiving service:
  Doesn't know about 'phone' field
  Might ignore it (fine)
  Or crash if it's required (bad)
```

**Why this matters in interviews:** gRPC and protobuf are the standard for microservices at scale (Google, Uber, Spotify). Senior SWEs must understand wire format, forward/backward compatibility, and versioning strategies.

---

## First Principles: Why Protocol Buffers

HTTP + JSON:
- Human readable
- Flexible (any field can be any type)
- Bloated: `{"user_id": 123}` is 20 bytes
- Slow to parse: must read every character

Protocol Buffers:
- Binary format (compact)
- Strongly typed (schema enforced)
- Fast to parse (field tags, not names)
- Versioning built-in (field numbers don't change)

**Wire format example:**

```
JSON:
{"user_id": 123, "email": "user@example.com"}
(size: ~45 bytes)

Protobuf:
[0x08, 0x7B, 0x12, 0x12, 0x75, 0x73, 0x65, 0x72, ...]
(size: ~15 bytes)

Field tags:
  user_id = field 1 (0x08 = tag 1)
  email = field 2 (0x12 = tag 2)
```

---

## Protobuf Message Format

```protobuf
syntax = "proto3";

message User {
  int32 user_id = 1;
  string email = 2;
  string phone = 3;
  int64 created_at = 4;
}
```

**Key insight:** Field numbers (1, 2, 3, 4) are permanent. Names can change, but numbers cannot.

**Wire encoding:**

```
Message: {user_id: 123, email: "user@example.com"}

Binary:
[0x08, 0x7B]                          // Field 1 (user_id), value 123
[0x12, 0x12, 'u', 's', 'e', 'r', ...] // Field 2 (email), string "user@example.com"

Format:
  (field_number << 3) | wire_type
  (1 << 3) | 0 = 0x08 (field 1, wire type 0 = varint)
  (2 << 3) | 2 = 0x12 (field 2, wire type 2 = length-delimited)
```

**Wire types:**
- 0: varint (integers)
- 2: length-delimited (strings, nested messages)
- 5: 32-bit fixed (float)

---

## gRPC: Streaming RPC

Unlike REST (request → response), gRPC supports 4 modes:

```protobuf
service UserService {
  // Unary (like REST)
  rpc GetUser(UserID) returns (User);
  
  // Server streaming
  rpc ListUsers(Filter) returns (stream User);
  
  // Client streaming
  rpc UploadUsers(stream User) returns (Status);
  
  // Bidirectional streaming
  rpc SyncUsers(stream User) returns (stream User);
}
```

**Diagram: gRPC Streaming Patterns**

```
Unary RPC:
  Client sends 1 request
  Server sends 1 response
  Connection closed
  
  Timeline: [request] → [response]
  Latency: 1 RTT + processing

Server streaming:
  Client sends 1 request
  Server sends stream of responses
  
  Timeline: [request] → [response 1]
                      → [response 2]
                      → [response 3]
                      → EOF
  
  Use case: List all users (10K users in 1 stream)
  Benefit: No pagination, client controls flow

Client streaming:
  Client sends stream of requests
  Server sends 1 response
  
  Timeline: [request 1] → 
            [request 2] → [response with summary]
            [request 3] →
  
  Use case: Upload 1M events in batch
  Benefit: Single response reduces round-trips

Bidirectional streaming:
  Client sends stream, server sends stream
  Both asynchronous
  
  Timeline: [req 1] ↔ [resp 1]
            [req 2] ↔ [resp 2]
            [req 3] ↔ [resp 3]
  
  Use case: Chat, multiplayer game, real-time sync
  Benefit: Full duplex communication
```

---

## Schema Evolution: Forward & Backward Compatibility

**Rule 1: Never reuse field numbers**

```protobuf
// v1 (released)
message User {
  int32 user_id = 1;
  string email = 2;
}

// v2 (DO NOT DO THIS):
message User {
  int32 user_id = 1;
  string phone = 2;  // WRONG! Reused field 2
}

// v2 (CORRECT):
message User {
  int32 user_id = 1;
  string email = 2;
  string phone = 3;  // New field, new number
}
```

**Why:** Old services send field 2 as email (string). New service reads field 2 as phone. Parsing fails.

**Rule 2: Make new fields optional or have defaults**

```protobuf
// v1
message User {
  int32 user_id = 1;
  string email = 2;
}

// v2 - old service sends only fields 1,2
// new service receives:
message User {
  int32 user_id = 1;
  string email = 2;
  int64 created_at = 3;  // Default: 0
  string phone = 4;       // Default: ""
}

// Old client (doesn't know about fields 3, 4):
User old_user = deserialize([0x08, 0x7B, 0x12, 0x12, ...])
// Unknown fields are skipped
// Result: user_id=123, email="", created_at=0, phone=""
```

**Forward compatibility:** Old code reads new messages (unknown fields ignored).
**Backward compatibility:** New code reads old messages (missing fields get defaults).

---

## Deadlines & Timeouts

gRPC enforces request deadlines (unlike REST):

```go
// Client side: Set deadline
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

response, err := client.GetUser(ctx, &UserID{Id: 123})
// If response takes > 5s, request is cancelled
```

**Diagram: Deadline Propagation**

```
Client → Upstream Service → Database

Client sets deadline: t=5s
  ↓
Upstream service receives deadline: t=4.8s (already used 200ms)
  Adjusts own deadline to 4.5s (leave buffer)
  ↓
Upstream queries DB with deadline: t=4.5s
  Database knows: if query > 4.5s, cancel

Result: Cascading deadlines prevent wasted queries
```

**Benefit:** No "hanging" requests. If upstream is slow, downstream knows to cancel early.

---

## Failure Scenario: Schema Mismatch Cascade

```
Timestamp: Saturday, 10 PM (peak traffic)

Service A deployed with new User schema:
  message User {
    int32 id = 1;
    string email = 2;
    int64 created_at = 3;  // NEW FIELD
  }

Service B not yet updated (old schema):
  message User {
    int32 id = 1;
    string email = 2;
  }

Service C also old:
  message User {
    int32 id = 1;
    string email = 2;
  }

A → B RPC:
  A sends: {id: 123, email: "user@example.com", created_at: 1697123456}
  B receives: {id: 123, email: "user@example.com"}
  (created_at is unknown field, skipped silently)
  
  Works fine (forward compatible)

B → C RPC:
  B sends: {id: 123, email: "user@example.com"}
  C receives: {id: 123, email: "user@example.com"}
  
  Works fine

A → C RPC (direct):
  A sends: {id: 123, email: "user@example.com", created_at: 1697123456}
  C deserializes with old proto definition
  C crashes? Or ignores created_at?
  
  If C doesn't have the proto file updated, it crashes
```

**Detection:** Add monitoring for proto version mismatch.

**Prevention:** 
- Deploy services in order (bottom-up dependency order)
- Test with multiple proto versions
- Monitor error rates during rollout
- Canary new schema to 1% of traffic first

---

## Interview Pattern: Schema Migration

```
Q: "You have 50 microservices using User proto.
   You need to add a new field (phone: string).
   100K requests/sec across services.
   How do you roll this out without downtime?"

Weak answer:
  "Deploy the new schema to all services at once"
  (❌ Risk of incompatibility if deployment order is wrong)
  
  Or: "Add the field and mark it deprecated"
  (❌ Deprecated fields confuse developers)

Strong answer:
  "Zero-downtime migration:
  
  1. Update proto definition (add phone field):
     message User {
       int32 id = 1;
       string email = 2;
       string phone = 3;  // NEW, optional
     }
  
  2. Deploy consumers first (bottom-up):
     - Services that READ User proto need to handle new field
     - Deploy: auth_service, profile_service (read User)
     - New code: ignores phone field (backward compatible)
  
  3. Deploy producers second:
     - Services that CREATE User proto
     - Deploy: user_service (creates User)
     - New code: populates phone field if available
  
  4. Verify with canary:
     - Deploy user_service to 1% of traffic
     - Monitor error rate for 5 minutes
     - If stable, ramp to 100%
  
  5. Backfill old records (async):
     - Update existing users in database
     - Set phone field to empty string or fetch from source
  
  6. Monitor:
     - Track proto version distribution (expect 50→48→50 during rollout)
     - Alert if version skew > threshold
     - Check error rate spike
  
  Why this works:
  - Consumers ready before producers send new field
  - Old consumers can handle new messages (proto forward compat)
  - New consumers can handle old messages (proto backward compat)
  - No mandatory version sync across 50 services
  - Canary validates before full rollout

Why this signals good judgment:
  - You understand proto compatibility rules
  - You know deployment order matters
  - You use canary to reduce risk
  - You have rollback plan (if error rate spikes, revert producer)
  - You don't rush deployment"
```

---

## gRPC vs HTTP/2: Performance

```
Traditional REST (HTTP/1.1):
  - Text-based (verbose)
  - Headers sent with every request
  - Slow serialization (JSON parse every field)
  
gRPC (HTTP/2 + Protobuf):
  - Binary (compact)
  - Headers sent once (stream multiplexing)
  - Fast serialization (binary encoding)
  - Connection reuse (persistent)

Latency comparison:
  REST call: serialize JSON (1ms) + send (2ms) + parse (1ms) = 4ms
  gRPC call: serialize proto (0.1ms) + send (0.5ms) + parse (0.1ms) = 0.7ms
  
  5-6x faster
```

---

## Checklist: gRPC & Protobuf Design

- [ ] Proto schema matches service boundaries (one proto per domain)
- [ ] Field numbers never reused (even if field is deleted)
- [ ] New fields are optional with sensible defaults
- [ ] Streaming RPC used for bulk operations (not pagination)
- [ ] Deadlines enforced on client side (timeout strategy)
- [ ] Deployment order documented (consumers before producers)
- [ ] Schema changes tested with old + new versions
- [ ] Monitoring for proto version mismatch (canary checks)
- [ ] Error handling explicit (not silent field drops)

## Common Wrong Answers

1. **"Just deploy all services at once"**
   - Risk of incompatibility
   - Can't rollback atomically across 50 services

2. **"Reuse field numbers for renamed fields"**
   - Classic mistake, causes parsing failures
   - Field numbers are permanent

3. **"Make all fields required"**
   - Breaks backward compatibility
   - Old clients can't send empty fields

4. **"Use JSON for internal APIs"**
   - Performance penalty (10x larger messages)
   - Schema evolution less explicit

5. **"Deprecate fields by deleting them"**
   - Old clients crash
   - No safe way to remove field
   - Better: mark deprecated and ignore

6. **"Don't need deadline timeouts"**
   - Requests hang indefinitely
   - Cascading failures (downstream doesn't know upstream is stuck)
