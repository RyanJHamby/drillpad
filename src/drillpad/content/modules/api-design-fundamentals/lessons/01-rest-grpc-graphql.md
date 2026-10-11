# API Design: REST vs gRPC vs GraphQL

## Quick Comparison

```
                REST          gRPC          GraphQL
Latency         High          Low           Medium
Bandwidth       High          Low           Medium
Complexity      Low           Medium        High
Caching         Excellent     Hard          Medium
Client gen      Manual        Auto          Auto
Use case        Web APIs      Internal      Flexible queries
```

## REST (REST for web APIs)

```
GET /orders/123

Pros:
  - Simple, cacheable (HTTP caching)
  - Easy to debug (browser, curl)
  - CDN-friendly
  
Cons:
  - Multiple round-trips (N+1 queries)
  - Over-fetching (you get whole object)
  - Versioning complexity

When:
  - Public APIs, web browsers
  - Cache-friendly (200k orders cached by CDN)
```

## gRPC (Internal high-performance APIs)

```
rpc GetOrder(GetOrderRequest) returns (OrderResponse) {}

Pros:
  - Low latency (protobuf binary)
  - Single round-trip
  - Auto code generation
  
Cons:
  - Hard to cache (binary protocol)
  - Requires HTTP/2
  - Not browser-friendly

When:
  - Internal microservices
  - Low-latency critical (order matching)
  - High throughput (1M+ req/sec)
```

## GraphQL (Flexible queries)

```
query {
  order(id: 123) {
    id
    symbol
    quantity
  }
}

Pros:
  - Client specifies what it needs (no over-fetch)
  - Single query (no N+1)
  - Introspection (self-documenting)
  
Cons:
  - Complex backend (query planning)
  - Hard to cache (flexible queries)
  - Learning curve

When:
  - Multiple clients with different needs
  - Mobile (reduce bandwidth)
  - Exploration (dashboards, analytics)
```

## Trading Interview: API Choice

```
Q: "Design API for order matching system"

Answer structure:
  "Internal service → gRPC (low-latency)
   Web dashboard → REST with caching
   Mobile app → GraphQL (bandwidth-constrained)
   
   Why gRPC internal:
   - 1M orders/sec, need <1ms latency
   - gRPC vs REST: 10x latency difference at scale
   
   Why REST for web:
   - CDN can cache /orders/123
   - Reduces backend load
   
   Why GraphQL mobile:
   - Mobile needs specific fields only
   - GraphQL returns exactly what's requested
   - Reduces bandwidth ~60%"
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "Use REST for everything" (ignores tradeoffs)
- "gRPC is always better" (not for browser, caching)
- "GraphQL solves all problems" (complex, cache-hard)

✅ **Green flags:**
- "REST for public APIs, gRPC for internal"
- "Choose based on latency, caching needs, client type"
- "REST + GraphQL hybrid (use each where it wins)"

