# Service Mesh: Sidecars, L7 Routing, Observability & Load Balancing

## The Problem

You have 50 microservices. Each one needs to:
- Load balance requests
- Retry failed requests
- Circuit break on errors
- Log request latency
- Enforce rate limits
- Handle timeouts
- Authenticate calls

Do you add this to every service (50x code duplication)? Or do you abstract it into infrastructure?

**Service mesh** abstracts this: infrastructure that manages service-to-service communication.

```
Without mesh:
  Service A must handle:
    - Connect to B
    - Load balance across B instances
    - Retry on failure
    - Circuit break
    - Timeout
    - Auth
    
  Code bloat: 50+ lines per RPC call
  Duplicated across 50 services = 2,500+ lines of boilerplate

With mesh:
  Service A sends RPC to B (normal code)
  Sidecar proxy intercepts (transparent)
  Sidecar proxy handles:
    - Load balancing
    - Retries
    - Circuit breaking
    - Timeouts
    - Auth
    - Observability
  
  Service code: unchanged, clean
  Infrastructure: centralized in Envoy/Istio
```

**Why this matters:** At scale (100+ services), service mesh is essential. Trading platforms, payment systems, AI infrastructure all use mesh. Understand trade-offs before adopting.

---

## First Principles: Sidecar Proxy Architecture

Traditional load balancer (client library):

```
Service A                    Service B
  ├─ Business code           ├─ Listener on :8080
  ├─ gRPC client library
  │   ├─ Load balancer       Service B instance 2
  │   ├─ Retry logic         ├─ Listener on :8081
  │   ├─ Circuit breaker
  └─ Observability          Service B instance 3
                             ├─ Listener on :8082
```

**Problem:** Logic is in the client. Every client library must implement. Each language is different.

Sidecar proxy (infrastructure):

```
Service A                    Sidecar proxy (Envoy)
  ├─ Business code             ├─ Load balancer
  └─ gRPC client               ├─ Retry logic
        ↓                       ├─ Circuit breaker
  Sidecar proxy (Envoy)         └─ Observability
    ├─ Load balancer               ↓
    ├─ Retry logic           Service B instances
    ├─ Circuit breaker           ├─ :8080
    └─ Observability            ├─ :8081
        ↓                         └─ :8082
    Service B
```

**Advantage:** Logic is in one place (Envoy). Works for any language/client.

---

## Sidecar Proxy: Envoy

Envoy is a proxy that intercepts traffic between services:

```
Setup:
  1. Deploy Envoy sidecar alongside each service (Pod in K8s)
  2. Envoy listens on localhost:15001 (virtual port)
  3. Service connects to localhost:15001
  4. Envoy intercepts, forwards to actual service B
  5. All logic (load balance, retry, etc.) in Envoy

Traffic flow:
  Client RPC → localhost:15001 (Envoy)
            → Envoy LB chooses: B instance 1
            → Envoy connects to B:8080
            → Receives response
            → Returns to client

Why localhost?
  Fast (no network latency)
  Secure (eBPF/netfilter redirects)
  Simple (TCP localhost connection)
```

**Diagram: Envoy Sidecar in Service Mesh**

```
Pod (Kubernetes):
  ┌─────────────────────────────────┐
  │ Container: Service A            │
  │  ├─ Process                     │
  │  └─ Connect to :15001           │
  │                                 │
  │ Container: Envoy Sidecar        │
  │  ├─ Listen on :15001            │
  │  ├─ Load balance                │
  │  ├─ Route to upstream services  │
  │  └─ Observability (metrics)     │
  └─────────────────────────────────┘
      ↓ (via eBPF/netfilter)
  Other services (B, C, D)
```

---

## L7 Routing (Layer 7 / Application Layer)

Unlike L4 (transport layer, just TCP), L7 routing inspects the **application protocol** (HTTP, gRPC).

**L4 routing:** "Send TCP connections to Server A or B" (no awareness of HTTP)

**L7 routing:** "Send HTTP requests to Service A based on path, or Service B based on host header"

**Example: Route by HTTP path**

```
Incoming request: POST /api/users/123
Sidecar Envoy inspects: path = /api/users/*
Routing rule: /api/users/* → user-service
Forwards to: user-service:8080

Incoming request: GET /api/products
Sidecar Envoy inspects: path = /api/products*
Routing rule: /api/products* → product-service
Forwards to: product-service:8080
```

**Benefits:**
- Request-level routing (not connection-level)
- Retry with payload awareness
- Timeout per RPC
- Load balance at RPC level

**Diagram: L7 Routing Rules**

```
Service A (frontend):

GET /api/users → User Service (service_users:8080)
GET /api/products → Product Service (service_products:8080)
GET /api/orders → Order Service (service_orders:8080)

Envoy receives: GET /api/users/123?limit=10
  1. Parse HTTP path: /api/users
  2. Match routing rule: GET /api/users → User Service
  3. Forward to: service_users:8080
  4. Retry on 5xx (max 3 attempts)
  5. Timeout: 10s per request
  6. Return response to client

All at L7 (application awareness)
```

---

## Observability: Metrics & Tracing

Service mesh generates metrics automatically:

```
Envoy collects:
  - Request latency (p50, p99, p99.9)
  - Error rate (4xx, 5xx)
  - Throughput (requests/sec)
  - Payload size

Examples:
  envoy_http_downstream_rq_time{service="user_service"}
    [50ms, 100ms, 200ms, 500ms, 1000ms, 5000ms]
    p50=100ms, p99=500ms, p99.9=5000ms
  
  envoy_http_downstream_rq_total{status="500"}
    10 errors
  
  envoy_http_downstream_rq_total{}
    1000 total requests
```

**Distributed tracing:** Each RPC is traced end-to-end

```
Client request to user-service:
  1. Client calls user-service
  2. Sidecar adds trace header: X-Trace-ID=abc123
  3. user-service processes, calls product-service
  4. user-service adds trace header to downstream call
  5. product-service processes
  6. All three services (client sidecar, user sidecar, product sidecar) report latency
  
Result: Full path visible
  Client → user-service (50ms)
  user-service → product-service (30ms)
  Total: 80ms
```

---

## Failure Scenario: Service Mesh Causes Cascading Failures

```
Setup:
  - 50 services, all using Envoy sidecars
  - Services B and C are critical
  - Envoy control plane (Istio, Consul) goes down

What happens:
  t=0: Control plane crash
  t=10s: Envoy caches expire
  t=10s: Envoy can't reach control plane (no config updates)
  
  Option 1: Fail closed (stop routing)
    All services stop working
    Outage immediately visible
  
  Option 2: Fail open (use cached config)
    Services keep working
    If cached config is stale, routing is wrong
    Silent failures

Traditional approach (client library):
  No control plane, logic in client
  Services keep working (no SPOF)
  But can't update routing rules dynamically

Service mesh approach (sidecar):
  Control plane = SPOF
  But enables powerful policies (traffic mirroring, A/B testing)
```

**Prevention:**
- Redundant control planes (3+ instances)
- Cache config in Envoy (if control plane down, use cache)
- Fallback routing rules (e.g., round-robin to all known IPs)
- Monitoring: alert if Envoy can't reach control plane

---

## Interview Pattern: Service Mesh Migration

```
Q: "Your team wants to adopt Istio service mesh.
   You have 30 microservices with custom load balancing logic.
   Some services have retry, some don't; some have timeouts, some don't.
   How do you migrate safely?"

Weak answer:
  "Just deploy Istio and start using it"
  (❌ Risk: old code conflicts with mesh policies, silent failures)
  
  Or: "Don't migrate, keep client libraries"
  (❌ Misses benefits of unified infrastructure)

Strong answer:
  "Phased migration with safety checks:
  
  Phase 1: Deploy infrastructure (weeks 1-2)
    - Deploy Istio control plane (3 replicas)
    - Deploy Envoy sidecars on all pods (no policies yet)
    - Envoy starts proxying traffic (but no rules applied)
    - Observe: Check that p99 latency doesn't increase
    - Metrics: Sidecars should pass through traffic unchanged
  
  Phase 2: Migrate one service (weeks 3-4)
    - Choose low-risk service (not critical)
    - Disable client-side load balancer (use Envoy instead)
    - Keep client-side retry for now (Envoy also retries)
    - Test: chaos engineering, latency injection
    - Measure: Compare p99 latency (should be same)
  
  Phase 3: Migrate retry logic (weeks 5-6)
    - Update service code: remove retry logic
    - Add Envoy retry policy (3 attempts, exponential backoff)
    - Test: Verify retry behavior matches old code
    - Monitor: Error rate, retry distribution
  
  Phase 4: Migrate timeouts (weeks 7-8)
    - Remove client-side timeouts
    - Configure Envoy timeouts (10s default)
    - Per-RPC timeout in routing rules
  
  Phase 5: Advanced policies (weeks 9+)
    - Traffic mirroring (shadow traffic)
    - A/B testing (route 10% to new version)
    - Circuit breaking (automatic failover)
  
  Safety checks at each phase:
    - Latency monitoring (p50, p99, p99.9)
    - Error rate (4xx, 5xx)
    - Throughput (requests/sec)
    - Distributed tracing (end-to-end)
    - Canary deployment (1 pod → 10% traffic → 50% → 100%)
  
  Rollback plan:
    - If latency increases > 10%, rollback
    - If error rate increases, rollback
    - Keep old code around for 2 weeks (in case)
  
  Why this works:
    - Gradual migration (lower risk)
    - Overlapping logic is caught (retries double, but monitored)
    - Safety checks at each step
    - Can rollback if something breaks
  
  Cost:
    - Envoy CPU: ~1-5% per pod
    - Latency: +1-2ms (loopback overhead)
    - Complexity: Istio adds new failure modes (control plane)
  
  ROI:
    - Unified policies (retry, timeout, circuit break)
    - Dynamic traffic control (A/B testing, canaries)
    - Observability (automatic metrics, tracing)
    - Reduced code duplication (30 services × 500 lines)"

Why this signals good judgment:
  - You understand the risk (dual-implementation of logic)
  - You have a phased approach (not all-or-nothing)
  - You monitor at each step (catches problems early)
  - You can rollback (prepared for failure)
  - You measure ROI (is it worth the complexity?)
```

---

## Trade-offs: Service Mesh vs Client Library

| Aspect | Client Library | Service Mesh (Envoy) |
|--------|----------------|---------------------|
| **Deployment** | Ships with service | Separate sidecar |
| **Configuration** | Code/config files | Centralized (Istio) |
| **Languages** | Different per language | Universal (proxy) |
| **Latency** | Direct connection | +1-2ms (loopback) |
| **Complexity** | Code complexity | Infrastructure complexity |
| **Control plane** | No SPOF | Control plane = SPOF |
| **Observability** | DIY (each service) | Built-in (Envoy stats) |
| **Dynamic policies** | Hard (code deploy) | Easy (config change) |
| **Debugging** | Familiar (code) | Complex (proxy) |

---

## Checklist: Service Mesh in Production

- [ ] Control plane is redundant (3+ replicas)
- [ ] Envoy sidecars deployed on all pods
- [ ] Metrics collected and stored (Prometheus)
- [ ] Distributed tracing set up (Jaeger/Zipkin)
- [ ] Canary deployment tested (gradual traffic shift)
- [ ] Failure scenarios tested (control plane down, sidecar down)
- [ ] Latency impact measured (p99 must be < 5% increase)
- [ ] Rollback procedure documented (how to disable mesh)
- [ ] Team trained on mesh debugging (how to read Envoy logs)

## Common Wrong Answers

1. **"Service mesh has no overhead"**
   - Sidecar adds 1-5ms latency
   - Adds CPU (10-30% per pod)
   - Worth it for large systems, not for small ones

2. **"Just enable all policies at once"**
   - Risk: unintended interactions (double retry)
   - Better: phased migration, canary rollout

3. **"Mesh replaces all load balancing"**
   - L7 routing doesn't replace L4 LB
   - Both needed (external LB + mesh LB)

4. **"Control plane failure is not a risk"**
   - If control plane is down, Envoys use cached config
   - But dynamic policies stop working (silent failure)
   - Need redundancy + monitoring

5. **"Service mesh is required for microservices"**
   - Useful at 20+ services
   - Small teams (< 5 services) don't need it
   - Know when to use it
