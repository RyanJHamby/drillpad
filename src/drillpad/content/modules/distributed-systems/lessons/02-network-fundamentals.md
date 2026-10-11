# Network Fundamentals: TCP, Latency, Packet Loss, Congestion

## Typical Contexts: trading systems, cloud platforms, and large-scale web infrastructure

**Problem:** Send data from A to B over network. Network has latency, packet loss, and jitter. What can go wrong?

- **Latency:** A waits forever for B's response (timeout?)
- **Packet loss:** Data arrives corrupted or not at all (retransmit?)
- **Congestion:** Too many packets, switch drops some (backpressure?)
- **Reordering:** Packets arrive out of order (sequence numbers?)

**Why hard:** Network is unreliable; you must assume everything can fail.

---

## TCP Handshake (3-Way)

```
Normal:
  A (client): SYN → B (server)
  B: [receive] ACK + SYN → A
  A: [receive] ACK → B
  A + B: connection established
  
Total round trips: 2 RTT (if RTT = 50ms, connection setup = 100ms)

With packet loss:
  A: SYN → [lost]
  A: [timeout 100ms] SYN → B
  B: ACK + SYN → A
  A: ACK → B
  Connection established, but took 100ms+ instead of 50ms
```

---

## Latency Components

```
Total latency = propagation + serialization + processing + queueing

Propagation:
  Speed of light = 3*10^8 m/s
  1000 km → 3.3 ms (one way)
  NYC to London: ~80ms round trip (fixed, can't improve)
  
Serialization:
  Send 1000 bytes at 10Gbps
  Time = 1000 bytes * 8 bits/byte / 10*10^9 bits/sec = 0.8 µs
  
Processing:
  Router/switch process time: 1-10 µs
  
Queueing:
  Packet arrives at switch with 100 packets already waiting
  Wait time: 100 packets * 10 µs = 1 ms
  (Most variable component!)

Example: 1 packet, 1000 km:
  Propagation: 3.3 ms
  Serialization: 0.8 µs
  Processing: 5 µs
  Queueing: 0 (no queue)
  Total: ~3.3 ms
  
Example: 1000 packets at congested switch:
  Propagation: 3.3 ms
  Serialization: 0.8 µs
  Processing: 5 µs
  Queueing: 1000 packets * 10 µs = 10 ms
  Total: ~13.3 ms (4x worse!)
```

---

## Packet Loss and Retransmission

```
TCP handles retransmission:
  A → B: "here is data"
  A: [wait for ACK]
  [packet lost]
  A: [timeout ~100ms] resend
  B: ACK → A
  A: [receive] ACK, ok

RTO (Retransmission Timeout):
  TCP estimates RTT
  RTO = RTT * 2 (with margin)
  
RTT = 50ms → RTO = 100ms
RTT = 200ms → RTO = 400ms
RTT = 1s → RTO = 2s

Loss rate 1%: expected ~1 second extra latency per 100 packets
```

---

## Congestion Control (TCP Slowstart, Congestion Avoidance)

```
Window-based flow control:
  Sender has "congestion window" (cwnd)
  cwnd limits how many packets can be in flight
  
Slowstart:
  cwnd = 1
  Send 1 packet, get ACK → cwnd = 2
  Send 2 packets, get ACKs → cwnd = 4
  Send 4 packets, get ACKs → cwnd = 8
  ... exponential growth until loss
  
  Time to reach 100K packets/sec:
  Start: cwnd=1 (1 packet)
  RTT=50ms, so ~1 packet per 50ms
  Need log2(100K) = ~17 RTTs
  Total time: 17 * 50ms = 850ms
  
  After 850ms, finally achieve target throughput!

Congestion avoidance (after slowstart):
  cwnd grows linearly (not exponential)
  Packet loss → cwnd / 2 (back off)
  Recovery: slowly increase
```

---

## Measuring Network Latency

```
Ping (ICMP):
  $ ping google.com
  round_trip_min/avg/max/stddev = 20/25/40/5 ms
  
  Min: best case (low queueing)
  Avg: typical
  Max: worst case (high queueing)
  
Traceroute (hop-by-hop RTT):
  $ traceroute google.com
  1. Local gateway: 1 ms
  2. ISP router: 10 ms
  3. Backbone: 20 ms
  4. Google datacenter: 25 ms
  
  Can identify congested hop
  
TCP RTT vs ICMP RTT:
  ICMP: lightweight, different path treatment
  TCP: realistic for app traffic
  May differ 10-50%
```

---

## Real Pattern: Ultra-Low Latency Trading (Sub-Microsecond)

```
An order-book engine at a trading firm:

Network path: Exchange → Algorithm → Risk Check → Order Book

Latency budget: 1000 ns (1 microsecond)

1. Receive network packet: 100 ns (serialization)
2. Kernel processing: 100 ns (interrupt, context switch)
3. User-space processing: 300 ns (validate, route)
4. Risk check RPC: 200 ns (one-way to risk service)
5. Order book insert: 100 ns
6. Serialize response: 100 ns
7. Send back: 100 ns

Total: 1000 ns = 1 µs

How to achieve this?
  ├─ kernel bypass (DPDK, AF_XDP) → remove kernel
  ├─ CPU affinity → no context switch
  ├─ pre-allocation → no malloc
  ├─ local network → low propagation
  └─ high-speed NIC (100Gbps+) → low serialization
  
Normal TCP: ~100 µs (100x slower!)
Reason: kernel buffering, congestion, retransmits
```

---

## Debugging Network Issues

```
High latency:
  1. Measure one-way vs round-trip
     If RTT = 100ms but one-way should be 50ms → retransmits
  
  2. Check packet loss
     $ netstat -su | grep "packet loss"
     If > 0.1%: network issue
  
  3. Check queueing (ifstat)
     $ ifstat
     If rx/tx drops > 0: buffer overflow
  
  4. Check for retransmits (tcpdump)
     $ tcpdump -i eth0 'tcp[tcpflags] & tcp-ack != 0'
     Count retransmits in trace
  
Variable latency (jitter):
  Caused by: queueing, GC pauses, context switches
  Fix: CPU affinity, disable GC, dedicated NIC
```

---

## Implementation: TCP Socket with Timeout

```python
import socket
import time

def send_with_timeout(host, port, data, timeout=1.0):
    """Send data with timeout handling."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)  # timeout on receive
    
    try:
        # Connect (SYN, SYN+ACK, ACK = 3 round trips)
        start = time.time()
        sock.connect((host, port))
        connect_time = time.time() - start
        print(f"Connection took {connect_time*1000:.1f} ms")
        
        # Send data
        sock.sendall(data)
        
        # Receive response with timeout
        try:
            response = sock.recv(4096)
            return response
        except socket.timeout:
            print(f"Timeout after {timeout} seconds")
            return None
    
    finally:
        sock.close()

# Real usage: order submission with timeout
class OrderGateway:
    def __init__(self, host, port, timeout=0.001):  # 1ms timeout
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
    
    def submit_order(self, order):
        """Submit order with 1ms timeout."""
        try:
            response = send_with_timeout(
                self.host, self.port,
                order.encode(), 
                timeout=self.timeout
            )
            return response
        except Exception as e:
            # Timeout or connection error
            # Queue for retry (async)
            return None
```

---

## Design Decisions

**Why TCP over UDP for trading?**
- TCP: guaranteed delivery, ordered, no duplicates
- UDP: faster (no retransmits) but unreliable
- For critical orders: TCP
- For market data feed: UDP (missing tick is ok)

**Why congestion control matters?**
- Without: sender floods network, packet loss spikes
- With: gradual ramp-up, fairer sharing

**Why queueing is latency's worst enemy?**
- Queueing is variable (depends on load)
- Cannot optimize what you can't measure
- Solution: active queue management (AQM), RED

**Why RTT measurements matter?**
- RTT baseline = network health
- RTT spike = congestion or packet loss
- Track RTT histogram, not just average

---

## Q&A

**Recall 1:** TCP handshake takes 3 round trips. RTT = 50ms. How long to connect?

*Must-say:*
- SYN → B: 50ms
- SYN+ACK → A: 50ms
- ACK → B: 50ms
- Total: 150ms (3 * RTT)
- Plus: serialization ~0.1ms
- Practical: ~150ms per connection

**Probe 1:** Congestion window grows exponentially in slowstart. cwnd=1 → 2 → 4 → 8. RTT=10ms. How long to reach cwnd=1000?

*Expected:*
- cwnd=1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024
- That's 10 doublings (2^10 = 1024)
- Time: 10 RTTs * 10ms = 100ms
- After 100ms, can send 1000 packets/RTT

**Numeric 1:** Packet loss = 1%. Average RTT = 50ms. Expected retransmit timeout = 100ms. For 10K packets, how many retransmits?

*Working:*
- 1% loss = 100 packets lost (out of 10K)
- Each retransmit adds 100ms
- But TCP batches: retransmits 3 packets together (fast retransmit)
- So ~33 retransmit events * 100ms = 3300ms extra
- Plus: slowstart recovery (exponential backoff)
- Practical impact: 3-5 seconds delay for 10K packets

---

## Questions for the Interviewer

- What's your typical RTT to the exchange? (measured how?)
- Do you use TCP or custom protocol?
- Have you had packet loss issues? (how did you detect?)
- Do you measure latency percentiles? (P50, P99, P99.9?)
- What's your worst-case network latency SLA?
- Do you use kernel bypass (DPDK, AF_XDP)?

