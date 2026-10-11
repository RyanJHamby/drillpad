# Network Protocols: TCP Slow Start & Congestion Control

## Why Network Latency Varies

Single RTT (round-trip time) = ~10-100ms depending on distance. But actual latency depends on congestion window size and packet loss.

```
New TCP connection:
  Client sends SYN → Server
  Server sends SYN-ACK → Client
  Client sends ACK → Server
  (3-way handshake = 1-3 RTTs, ~30-300ms)

Then data transfer starts
  But how much data per RTT?
```

## TCP Slow Start

New connection starts conservatively: send 1 segment (1 MSS ≈ 1500 bytes).

```
RTT 1: Send 1 segment (1 MSS)
       Receive ACK for 1
       cwnd (congestion window) = 2

RTT 2: Send 2 segments
       Receive ACK for 2
       cwnd = 4 (doubles each RTT)

RTT 3: Send 4 segments
       Receive ACK for 4
       cwnd = 8

RTT 4: Send 8 segments
       ...
       cwnd = 16

Exponential growth until:
  - Slow start threshold (ssthresh) reached
  - Packet loss detected
  - Time exceeded
```

## Real Example: Market Data Feed

```
Trading firm needs 100MB market snapshot every 100ms.

Scenario 1: Single TCP stream
  RTT = 10ms (same data center)
  Packet size = 1500 bytes
  
  RTT 1: cwnd=1   → 1.5 KB
  RTT 2: cwnd=2   → 3 KB
  RTT 3: cwnd=4   → 6 KB
  RTT 4: cwnd=8   → 12 KB
  RTT 5: cwnd=16  → 24 KB
  RTT 6: cwnd=32  → 48 KB
  RTT 7: cwnd=64  → 96 KB
  RTT 8: cwnd=128 → 192 KB (still ramping)
  
  Only after ~100ms do you get full bandwidth
  
  BUT: New connection every 100ms?
  → Slow start restarts each time
  → Peak throughput never reached

Scenario 2: Persistent connection + pipelining
  First 100ms: ramp up (slow start)
  After 100ms: full bandwidth maintained
  Next 100ms snapshot: already at cwnd=128, instant throughput
  
  Result: 60x+ speedup vs new connection per snapshot
```

## Congestion Control: Additive Increase, Multiplicative Decrease (AIMD)

After slow start reaches ssthresh, congestion avoidance:

```
Packet lost? → Multiplicative decrease
  cwnd = cwnd / 2
  
RTT passed without loss? → Additive increase
  cwnd = cwnd + 1

Graphic (over time):
  cwnd
   |      ╱╲
   |     ╱  ╲
   |    ╱    ╲
   |   ╱      ╲__
   |  ╱          ╲__  
   | ╱              ╲
   |╱________________╲_____ time
   
   Ramp up + crash on loss + recover
```

**Why asymmetric (2x down, +1 up)?** Prevents networks from thrashing. One loss event cuts bandwidth in half, but recovery is gradual.

## Real Impact: Cross-Region Latency

```
Same data center: 10ms RTT
  Slow start finishes in 100ms
  
Cross-region (US-EU): 150ms RTT
  Slow start takes: 150ms × 8 = 1.2 seconds to reach peak
  
  If messages sent every 500ms:
    New connection every time
    Slow start restarts
    Never reach peak bandwidth
```

**Fix:** Persistent connection + connection pooling

## Interview Questions

**Q: "Why does the first request to a service feel slow, then subsequent requests are fast?"**

A: "Slow start ramps congestion window exponentially (1→2→4→8...). First RTT sends 1 MSS, doubling each RTT until slow-start threshold. Only after ~log(N) RTTs is peak bandwidth reached. Subsequent requests on same connection skip slow start, so latency drops. For HTTP/1.1 without keep-alive, you pay slow start per request."

**Q: "How would you optimize latency for a market data feed with 100ms snapshot intervals?"**

A: "Persistent TCP connection (avoid 3-way handshake + slow start per snapshot). Pipelining: send multiple snapshots before waiting for ACK. Connection pooling if feeding multiple services. Monitor packet loss (tcpdump, netstat -s) — even 0.1% loss triggers AIMD halving, spiking latency 2-10x."

**Q: "What's the difference between RTT and actual latency you measure?"**

A: "RTT is one-way delay. Measured latency is RTT + (data_size / bandwidth) + queueing delay at switch buffers. If congestion window is small (slow start), measured latency = RTT + (serialization delay for full cwnd payload). On congested links, buffer bloat adds hundreds of ms."
