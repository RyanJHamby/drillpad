# DNS, TLS, HTTP: Name Resolution to Encrypted Requests

## Overview

Every web request involves three layers of complexity:

1. **DNS:** Resolve domain name to IP address
2. **TLS handshake:** Encrypt the connection
3. **HTTP/2 & HTTP/3:** Multiplex multiple requests, reduce latency

This lesson covers why the first request is slow, how to optimize each layer, and real latency measurements.

---

## The Problem: First Request Latency

```
Browser: "GET example.com"

Step 1: DNS lookup
  Query: "What's the IP for example.com?"
  Path: Browser cache (hit or miss)
         → OS resolver cache (hit or miss)
         → Recursive resolver (ISP or 8.8.8.8)
         → Root nameserver → TLD nameserver → Authority nameserver
  Time: 0ms (cache hit) to 200ms (cold, multiple hops)

Step 2: TCP handshake (3-way)
  SYN → Server
  SYN-ACK ← Server
  ACK → Server
  Time: 1 RTT = 10-100ms (depending on distance)

Step 3: TLS handshake
  ClientHello → Server
  ServerHello + Certificate + KeyExchange ← Server
  Finished → Server
  Finished ← Server
  Time: 1-2 RTTs = 10-200ms

Step 4: HTTP request
  GET / → Server
  Response ← Server
  Time: 1 RTT = 10-100ms

Total: DNS (200ms) + TCP (10ms) + TLS (100ms) + HTTP (10ms) = 320ms for first request!
```

**Key insight:** Overhead dominates for small requests (e.g., 100 bytes of data = 320ms overhead, 3000x).

---

## DNS: Name Resolution

**DNS query path:**

```
Query: example.com → IP?

Browser cache:
  hit? → return immediately (0ms)
  miss? → ask OS

OS resolver cache (/etc/resolv.conf, systemd-resolved):
  hit? → return immediately (1ms)
  miss? → recursive query

Recursive resolver (8.8.8.8 or ISP):
  1. Query root nameserver: "Where's .com?"
     → Root: "Ask TLD server X.Y.Z"
  
  2. Query TLD nameserver: "Where's example.com?"
     → TLD: "Ask authority server A.B.C"
  
  3. Query authority nameserver: "What's example.com?"
     → Authority: "It's 93.184.216.34"
  
  4. Return to client: "93.184.216.34"

Time: 3 queries × ~50ms (per query) = 150ms
```

**DNS caching:**

```
Response includes TTL (Time To Live):
  DNS record valid for X seconds
  
Browser cache:
  TTL = 300 seconds (5 minutes, typical)
  
OS resolver cache:
  TTL = 600 seconds or system default
  
Recursive resolver:
  TTL = record's TTL (propagates caching)
```

**Real impact: HTTP Keep-Alive**

```
Sequential requests:

Request 1: DNS (150ms) + TCP (10ms) + TLS (100ms) + HTTP (10ms) = 270ms
Request 2: TCP (10ms) + TLS (100ms) + HTTP (10ms) = 120ms  (DNS cached)
Request 3: HTTP (10ms) = 10ms  (TCP + TLS reused, keep-alive)
Request 4: HTTP (10ms) = 10ms

Total: 270 + 120 + 10 + 10 = 410ms for 4 requests
Average: 100ms per request

Without keep-alive:
Request 1: 270ms
Request 2: 270ms (DNS + TCP + TLS from scratch)
Request 3: 270ms
Request 4: 270ms
Total: 1080ms for 4 requests
Average: 270ms per request (2.7x slower!)
```

---

## TCP Handshake (Revisited)

**3-way handshake cost:**

```
Time 0: Client sends SYN
        Seq=1000, Flag=SYN, Payload=0

Time 10ms: Server sends SYN-ACK
           Seq=2000, Ack=1001 (client's seq + 1)

Time 20ms: Client sends ACK
           Seq=1001, Ack=2001, Payload=HTTP request (piggyback)

Time 30ms: Server sends response

Total: 30ms for handshake + request/response

Modern optimization: TCP Fast Open (TFO)
  Client knows server key from past connection
  Send data in SYN (cookie verification)
  Server can respond immediately if cookie valid
  Cost: 10ms (1 RTT, not 2)
  [VERIFY: Cookie overhead]
```

---

## TLS Handshake: The Expensive Part

**TLS 1.3 handshake (modern, simplified):**

```
Time 0: ClientHello
  - Supported cipher suites
  - Key share (Diffie-Hellman public key)
  - Payload: ~500 bytes

Time 10ms: ServerHello + Certificate + Finished
  - Server's key share (Diffie-Hellman public key)
  - Server's X.509 certificate (2-4KB typical)
  - Digital signature proving server owns cert
  - Finished message (encrypted with derived key)
  - Payload: ~4KB

Time 20ms: Client sends Finished (encrypted)
  - Verification message proving client received server hello
  - Payload: ~100 bytes

Time 30ms: Connection encrypted, HTTP request can go

Total: 30ms (1.5 RTTs)
```

**TLS certificate size and parsing:**

```
Typical certificate: 2-4KB
  - RSA public key (256-512 bytes)
  - Issuer chain (1-3 certs = 2-10KB total)
  
Cost:
  Network: 2KB over 10Mbps = 2ms
  Parsing: Certificate parsing = 100-500µs
  Verification: Signature check (RSA) = 10-50ms [slow!]
    RSA 2048-bit signature = ~10-20ms
    ECDSA 256-bit signature = ~1-2ms (faster)
```

**TLS session resumption (faster repeat connections):**

```
First connection:
  ClientHello → ServerHello + Certificate + Finished → Finished
  Cost: 1-2 RTTs (30-50ms)

Repeat connection (session cache):
  Browser remembers session ID or session ticket
  ClientHello (with session ID) → ServerHello (reuse) → Finished → Finished
  Cost: 1 RTT (10-30ms)
  
Session ticket (TLS 1.3):
  Server sends encrypted ticket after handshake
  Client can use ticket for next connection
  Server: no need to remember session state (stateless)
  Benefit: 0-RTT resumption with pre-shared key
```

---

## HTTP/1.1 vs HTTP/2 vs HTTP/3

**HTTP/1.1 (old, head-of-line blocking):**

```
Connection: keep-alive

GET /index.html
GET /style.css
GET /script.js
GET /image.png

Problem: Sequential processing
  1. Request 1 → Response 1 (100ms)
  2. Request 2 → Response 2 (50ms)
  3. Request 3 → Response 3 (50ms)
  4. Request 4 → Response 4 (100ms)
  
  Total: 300ms (sequential)
  
Head-of-line blocking: If response 1 is large, responses 2-4 wait
```

**HTTP/2 (multiplexing):**

```
Single TCP connection, multiple streams

GET /index.html (stream 1)
GET /style.css (stream 2)
GET /script.js (stream 3)
GET /image.png (stream 4)

All sent in parallel (interleaved in TCP stream)

Response handling (asynchronous):
  Stream 1 response arrives (100ms)
  Stream 2 response arrives (30ms)
  Stream 3 response arrives (30ms)
  Stream 4 response arrives (50ms)

Total: max(100, 30, 30, 50) = 100ms (parallel!)
Benefit: 3x faster than HTTP/1.1

Overhead: HTTP/2 framing (9-byte header per frame)
```

**HTTP/3 (QUIC protocol, UDP-based):**

```
TCP: Reliable but slow (multiple retransmits, head-of-line blocking)
QUIC (UDP-based):
  - Multiplexed streams (like HTTP/2)
  - Per-stream retransmission (packet loss on stream 1 doesn't block stream 2)
  - Connection migration (change network, connection stays alive)
  
TLS integration: TLS handshake in initial packet (0-RTT resumption)
  Client sends ClientHello with encrypted data
  Server processes immediately (no extra RTT)
  
Example (faster than HTTP/2 on cellular):
  Packet loss 0.1% (WiFi → cellular handoff)
  HTTP/2 over TCP: Loss on packet = retransmit, head-of-line blocking (10-100ms delay)
  HTTP/3 over QUIC: Loss on packet = retransmit that stream only (minimal impact)
```

---

## Connection Pooling & Persistence

**Why connection pooling matters:**

```
Scenario: Client makes 100 requests to service

Without pooling (new connection per request):
  100 requests × (TCP 10ms + TLS 50ms + HTTP 5ms) = 100 × 65ms = 6500ms

With pooling (1 connection, reused):
  TCP 10ms + TLS 50ms (one-time)
  + 100 × (HTTP 5ms) = 60ms + 500ms = 560ms
  
Benefit: 6500ms → 560ms = 12x faster!
```

**Real implementation (HTTP keep-alive):**

```cpp
// Open connection once
HttpConnection conn("example.com", 443);

// Reuse for multiple requests
for (int i = 0; i < 100; i++) {
  Response r = conn.get("/api/item/" + to_string(i));
  process(r);
}

// Connection timeout (usually 60-300 seconds)
// After timeout, new connection created automatically
```

---

## Q&A

**Q1: How much latency does DNS add?**

A: "0ms (cached) to 200ms (cold, multiple hops). Average real-world: 50-100ms. Optimization: use persistent DNS (avoid repeated queries), or pre-resolve (resolve during startup, not on-demand)."

**Q2: Is HTTP keep-alive automatic?**

A: "Yes, modern browsers and HTTP clients default to keep-alive. Server sends 'Connection: keep-alive' or no Connection header (HTTP/1.1 default). Timeout usually 60-300 seconds. After timeout, new connection created."

**Q3: When should I use HTTP/2 vs HTTP/3?**

A: "HTTP/2 for stable networks (datacenter, fiber). HTTP/3 for unreliable networks (cellular, WiFi). HTTP/3 lower latency on mobile (0-RTT, per-stream retransmit). HTTP/2 more compatible (older infrastructure). Real benchmark: HTTP/3 20-40% faster on poor network."

**Q4: What's the cost of TLS handshake vs TCP handshake?**

A: "TCP: 10-30ms (1 RTT). TLS: 30-100ms (1-2 RTTs depending on whether session resumption used). TLS dominates. Optimization: session resumption, session tickets, 0-RTT (if safe)."

**Q5: Should we use persistent DNS connections?**

A: "For high-throughput services: yes. DNS over TCP or HTTPS (DoH) persistent connections. Cost: 1 extra connection. Benefit: no DNS query latency (cached). Trade-off: memory overhead. Most web services don't bother (DNS cached at OS level)."

---

## Real Example: API Gateway Optimization

```
Setup: Mobile app makes API calls to service

Initial (every request new connection):
  DNS lookup: 100ms (cold)
  TCP: 10ms
  TLS: 50ms (no session resumption)
  API call: 50ms
  Total: 210ms per request

Optimization 1 (DNS caching):
  DNS lookup: 0ms (cached)
  TCP: 10ms
  TLS: 50ms
  API call: 50ms
  Total: 110ms per request

Optimization 2 (keep-alive):
  DNS lookup: 0ms
  TCP: 10ms (one-time)
  TLS: 50ms (one-time)
  API call: 50ms per request
  After first: 50ms per request (5x improvement)

Optimization 3 (session resumption):
  TLS: 30ms (session ticket)
  API call: 50ms
  Total: 80ms per request (2.6x improvement on TLS)

Optimization 4 (HTTP/2 multiplexing, batch requests):
  TLS: 30ms (one-time)
  4 requests in parallel (4 API calls): max(50, 50, 50, 50) = 50ms
  Total: 80ms for 4 requests (vs 80ms each for sequential = 320ms)
  Per request: 20ms (10x improvement!)
```

---

## Key Takeaways

1. **DNS adds 50-200ms** on cold cache (optimize with caching, persistent connections)
2. **TCP handshake: 10-30ms** (1 RTT, part of baseline)
3. **TLS handshake: 50-100ms** (1-2 RTTs, dominates for small requests)
4. **Session resumption halves TLS cost** (use session tickets)
5. **Keep-alive reuses connection** (avoid repeated handshakes)
6. **HTTP/2 multiplexes requests** (4 requests in parallel cost like 1)
7. **HTTP/3 reduces loss impact** (per-stream retransmit, better for mobile)

---

## Checklist

- [ ] Understand DNS lookup path (browser → OS → recursive → authoritative)
- [ ] Know TCP handshake cost and Fast Open optimization
- [ ] Understand TLS handshake steps (ClientHello → ServerHello → Finished)
- [ ] Know session resumption and session ticket benefits
- [ ] Understand HTTP/2 multiplexing vs HTTP/1.1 head-of-line blocking
- [ ] Know HTTP/3 QUIC benefits (per-stream retransmit, 0-RTT)
- [ ] Can estimate total latency (DNS + TCP + TLS + HTTP) for first vs repeat requests

## Common Wrong Answers

- "DNS lookup is cached automatically" ← Only if TTL > current time, must check
- "Keep-alive has no overhead" ← First request still pays handshake cost
- "HTTP/2 is always faster" ← On good networks, benefit is small (maybe 10-20% faster)
- "TLS is negligible overhead" ← No, it's often 50%+ of latency on fast networks
- "Session resumption is automatic" ← Client must remember session state (cookie/local storage)
