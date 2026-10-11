# CDN & Edge: Caching Strategies, Cache Invalidation, Latency Optimization

## Overview

CDNs (Content Delivery Networks) and edge computing move content close to users. This lesson covers:

1. **CDN fundamentals:** How caching reduces latency
2. **Cache invalidation strategies:** TTL, purge, versioning
3. **Origin shielding:** Protecting origin servers from traffic spikes
4. **Edge computing:** Running code at CDN locations
5. **Real latency measurements:** Impact of cache hits vs misses

---

## The Problem: Geographic Latency

**Without CDN (all requests go to origin):**

```
User in Sydney wants to download file from US origin (Los Angeles)

Network path:
  Sydney → Undersea cable → Los Angeles
  Latency: ~150ms (speed of light ~200,000 km/s in fiber)

Example: 1MB file download
  Bandwidth: 10Mbps (typical trans-Pacific)
  Download time: 1MB = 8 million bits / 10Mbps = 0.8 seconds
  Total latency: 150ms (RTT) + 800ms (transfer) = 950ms

Real impact: User sees slow page load (almost 1 second of waiting)
```

**With CDN (cache near user):**

```
Sydney CDN edge cache:
  User → Sydney edge cache (2ms local latency)
  Cache hit: serve 1MB from local cache
  Local download time: 1MB / 1Gbps (fast local) = 8ms
  Total latency: 2ms + 8ms = 10ms

Benefit: 950ms → 10ms = 95x faster!

Real impact: User sees instant page load
```

---

## CDN Caching Architecture

**Typical CDN (Cloudflare, Akamai, AWS CloudFront):**

```
Origin server (US, Los Angeles)
  │
  └─→ Origin shield (regional cache, Los Angeles)
      │
      ├─→ Edge cache (North America, San Francisco)
      ├─→ Edge cache (North America, Dallas)
      ├─→ Edge cache (Europe, London)
      ├─→ Edge cache (Asia, Tokyo)
      └─→ Edge cache (Australia, Sydney)

User in Sydney requests file.jpg:
  1. Check Sydney edge cache (local, 2ms)
  2. If miss: check Asia shield (Tokyo, 50ms latency)
  3. If miss: fetch from origin (Los Angeles, 150ms latency)
  4. Cache at each level on the way back
```

**Cache hierarchy impact:**

```
Scenario: Viral video, 100K users worldwide downloading same file

Worst case (no caching):
  Origin handles 100K requests simultaneously
  Origin bandwidth: 100K users × 1Mbps = 100 Gbps (impossible)
  Origin CPU: handling 100K connections (crashes)

With CDN (multi-level cache):
  Origin bandwidth: only cache misses
  Cache hit rate: 95% (99.95K cached)
  Origin bandwidth: 5K users × 1Mbps = 5 Gbps (manageable)
  Origin CPU: handling 5K connections (feasible)
  
  Actual path for user in Sydney:
    1. Request → Sydney edge (hit, serve immediately)
    2. Sydney edge populated from Asia shield (regional cache)
    3. Asia shield populated from origin (few requests)
```

---

## Cache Invalidation Strategies

**Problem: Stale content**

```
Scenario: Website v1 served from cache, then v2 deployed

Time 0: Deploy v2
  Origin has v2
  Edge caches still have v1 (TTL = 1 hour)
  
Time 0-60min: Users see v1 (stale!)
  50% get v1 from cache
  50% hit origin and get v2 (if origin updated)
  
Time 60min: TTL expires, caches fetch v2
  Users finally see v2
```

**Solution 1: Short TTL (Time To Live)**

```
Set Cache-Control: max-age=30  (30 second TTL)

Benefit: Stale content gone in 30 seconds
Cost: More requests to origin (cache misses every 30 seconds)

Trade-off:
  Short TTL (30s): Fresh content, high origin load
  Long TTL (1h): Stale content risk, low origin load
  
Real practice: 
  Static assets (images, CSS): 1 hour TTL
  HTML pages: 5-10 minutes TTL
  API responses: 30 seconds - 5 minutes TTL
  User data (personalized): no cache
```

**Solution 2: Purge on deployment**

```
API call: CDN provider API
  DELETE /cache/path/index.html
  
Effect: Immediately remove stale versions from all edge caches
  Time 0: Deploy v2, purge /index.html
  Time 0.1s: All edge caches purged
  Time 0.2s: Users get v2 (origin or refilled edge)

Benefit: Immediate cache invalidation
Cost: API calls to CDN provider, complexity

Real usage:
  Immediate purge: critical fixes (security, data corruption)
  Batch purge: daily deploys (every 10-100 files)
```

**Solution 3: Versioning (immutable URLs)**

```
v1: /assets/app.js (content: function foo() { return 1; })
v2: /assets/app.v2.js (content: function foo() { return 2; })

Set very long TTL: Cache-Control: max-age=31536000  (1 year)

On deployment:
  HTML page points to /assets/app.v2.js (different URL)
  Old URL still cached (v1)
  New URL fetched from origin and cached (v2)
  
Benefit: Unlimited TTL, no purges needed
Cost: URL scheme complexity, multiple versions in cache

Real usage:
  Git hash in filename: app.js.abc123def456.js
  Webpack/build tool generates versioned files
  HTML updated to reference new version
```

**Solution 4: Cache tags (Fastly, Cloudflare)**

```
Response headers:
  Cache-Tag: product:100, category:electronics

Purge command:
  PURGE /cache  (with Surrogate-Key: product:100)
  
Effect: All responses tagged with "product:100" purged at once

Example:
  Product page: Cache-Tag: product:100, user-data:false
  CDN: Serve from cache (TTL=1h)
  
  Product price updates: Purge Cache-Tag: product:100
  Edge: Remove all product:100 tagged responses
  
Benefit: Granular purging (don't purge unrelated content)
Cost: Requires CDN support (Fastly, Cloudflare Enterprise)
```

---

## Origin Shielding

**Problem: Cache stampede (thundering herd)**

```
Popular video cached at edge with TTL=1h
  100K users in Sydney all have same cache
  
Time 59m: Cache about to expire
Time 60m: TTL expires on all 100K cache entries

Next request arrives (from user 1):
  Cache miss
  User 1 requests from origin
  User 2 requests from origin (cache still loading)
  User 3 requests from origin
  ...
  User 100K requests from origin
  
Result: 100K simultaneous requests to origin (DDoS-like)
  Origin CPU spikes 100x
  Latency for each user: 50+ seconds
  Other regions affected (global origin overload)
```

**Solution: Origin shield (regional cache)**

```
Architecture:
  Edge cache (Sydney) → Shield cache (Asia/Tokyo) → Origin

With shield:
  Edge expires at 60m, requests shield
  Shield hasn't expired (different TTL, e.g., 2 hours)
  Shield serves all 100K edge cache misses
  
  Result: Origin sees only 1 request (from shield to refill)
  
Cost: Extra network hop (Sydney → Tokyo = 50ms)
  But only on cache misses (rare)
  
Real impact:
  99% cache hits: users unaffected
  1% cache miss: users get Tokyo latency (50ms) instead of origin (150ms)
  Origin load: reduced 100x
```

**Cache-Control header tuning:**

```
Scenario: Video service with 1M concurrent viewers

Header: Cache-Control: max-age=300, s-maxage=3600
  max-age: 300 (client-side, browser cache)
  s-maxage: 3600 (CDN cache)

Result:
  Browser expires after 5 minutes
  CDN edge expires after 1 hour
  CDN shield: separate expiry (often 24 hours)
  
Impact:
  User watches for 1 hour straight
  Browser cache expires after 5min, refetch from edge (hit)
  Edge cache expires after 1h, refetch from shield (hit)
  Shield refetch: happens off-peak, not during video playback
```

---

## Edge Computing

**Traditional model: Run code at origin**

```
Request: GET /api/user/123

Route to origin (Los Angeles)
  Latency: 150ms (geographic)
  Code runs: 50ms
  Return: 150ms
  Total: 350ms
```

**Edge computing: Run code at CDN edge**

```
Request: GET /api/user/123

Route to edge (Sydney)
  Latency: 2ms (local)
  Code runs (at edge, Cloudflare Workers, Lambda@Edge): 50ms
  If needs origin data: fetch from origin (150ms) + cache
  Return: 2ms
  Total: 54ms (6x faster!)
```

**Use cases for edge computing:**

```
1. Authentication/authorization
   - Verify JWT at edge (no origin needed)
   - Cost: ~50ms at edge vs 200ms round-trip to origin

2. Request routing
   - Route based on user location, device type
   - Cost: ~10ms at edge, avoids unnecessary origin hops

3. Image optimization
   - Resize, format convert (AVIF, WebP) at edge
   - Cost: ~100-500ms at edge, but offloads origin

4. Bot detection
   - Block suspicious requests at edge (before reaching origin)
   - Cost: ~5ms at edge vs DDoS at origin

5. Personalization (cache by cookie)
   - Different HTML for logged-in vs logged-out users
   - Cost: ~20ms edge logic vs cache invalidation nightmare
```

**Edge computing example (Cloudflare Workers):**

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);
  
  // Authenticate at edge
  const token = request.headers.get('Authorization');
  if (!isValidToken(token)) {
    return new Response('Unauthorized', { status: 401 });
  }
  
  // Cache by user ID (personalized cache)
  const userId = getUserId(token);
  const cacheKey = new Request(url, {
    headers: { 'Cache-Key': userId }  // Custom cache key
  });
  
  // Check cache
  let response = await caches.default.match(cacheKey);
  if (response) return response;
  
  // Fetch from origin
  response = await fetch(url);
  
  // Cache result
  await caches.default.put(cacheKey, response);
  
  return response;
}
```

---

## Q&A

**Q1: What TTL should I use for my API responses?**

A: "Depends on freshness requirement. Real-time data: 0-5 seconds (almost no caching). Stock prices: 10-60 seconds (delay acceptable). Catalog data: 5-10 minutes. Static assets: 1+ hours. Rule of thumb: shorter TTL = fresher content but more origin load. Start with 5 minutes, measure cache hit rate, adjust."

**Q2: How do I handle cache invalidation when deploying new code?**

A: "Three strategies: (1) Versioning (URLs with git hash, never purge). (2) Purge on deploy (API call to CDN). (3) Short TTL (5-10 min for HTML). Versioning is best for static assets, purge for critical fixes, TTL for balance."

**Q3: Is origin shielding worth the extra latency?**

A: "Yes if you have traffic spikes. Cost: +50ms latency on 1% requests (cache miss). Benefit: origin protected from 100x load spike (cache stampede). Break-even: if origin can't handle spike, shield prevents outage. If origin is robust, probably not needed."

**Q4: When should I use edge computing vs serving from origin?**

A: "Edge for latency-sensitive, lightweight operations (auth, routing, ~50ms max). Origin for heavy computation, database access (100-500ms+). Rule: if edge adds <100ms and saves origin RTT (150ms), worth it. Otherwise, origin is fine."

**Q5: How do I measure cache hit rate?**

A: "Check CDN dashboard (Cloudflare, AWS). Metrics: Cache Hit Rate = (cache hits) / (total requests). Target: 80%+ for static content, 50%+ for HTML, 0% for personalized/user-specific data. If <50%, either TTL too short or traffic pattern not cache-friendly."

---

## Real Example: Black Friday Traffic Spike

```
E-commerce site, normal traffic: 10K QPS (queries/sec)
Black Friday: 100K QPS expected (10x spike)

Setup (without CDN optimization):
  Origin capacity: 20K QPS (has 2x headroom)
  Expected: 100K QPS
  Problem: Overload by 5x

CDN strategy:
  1. Increase edge cache TTL (index: 1h, product pages: 30min)
  2. Enable origin shielding (regional caches)
  3. Implement cache tags (purge only changed products)
  
Result:
  Cache hit rate: 90% (9 out of 10 requests from edge)
  Origin load: 100K × 10% = 10K QPS (within capacity!)
  User latency: 10ms (edge) vs 200ms (origin + CDN overhead)

Without CDN:
  100K QPS → Origin overload → Users see 503 errors → Black Friday sales lost

With CDN:
  100K QPS → 90K from edge → 10K to origin → All requests served fast
```

---

## Key Takeaways

1. **CDN reduces latency by 90%+** (geographic + cache)
2. **Cache invalidation is hard** (stale content tradeoff)
3. **Versioning > purging > TTL** (in terms of complexity)
4. **Origin shielding prevents cache stampede** (regional intermediate cache)
5. **Edge computing offloads origin** (run lightweight code at CDN edge)
6. **Cache hit rate is key metric** (80%+ for static, 50%+ for dynamic)
7. **TTL should vary by content type** (assets: 1h, HTML: 5-10min, API: 30s-5min)

---

## Checklist

- [ ] Understand multi-level cache hierarchy (edge → shield → origin)
- [ ] Know TTL tradeoff (short = fresh but high load, long = stale risk but low load)
- [ ] Can explain versioning vs purging strategies
- [ ] Understand cache stampede and origin shielding solution
- [ ] Know when edge computing makes sense (latency-sensitive, lightweight)
- [ ] Can estimate cache hit rate impact on origin load
- [ ] Understand cache tags for granular invalidation

## Common Wrong Answers

- "Longer TTL is always better" ← No, exposes you to stale content and deployment risks
- "Cache invalidation is free" ← No, purges and revalidation have costs
- "Origin shielding adds too much latency" ← No, only 1% of requests (cache misses) affected
- "Edge computing eliminates origin" ← No, still need origin for cache misses and data
- "Cache hit rate > 99% is always achievable" ← No, depends on traffic pattern and TTL
