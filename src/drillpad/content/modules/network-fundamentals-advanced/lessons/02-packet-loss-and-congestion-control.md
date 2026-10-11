# Packet Loss & Congestion Control - When Networks Get Full

## Why Packet Loss Happens

Network link has limited bandwidth. When it fills up, packets get dropped.

```
Network link: 10 Gbps
Traffic: 9 Gbps (healthy)
One client sends: 2 Gbps (sudden spike)
Total: 11 Gbps needed, but only 10 Gbps available

Result: 10% of packets dropped
```

## Impact of Packet Loss

TCP (used by most internet):

```
Sender: "Here's packet 1"
Receiver: "Got it"
Sender: "Here's packet 2"
Receiver: [no response, packet dropped]
Sender: [waits, then retransmits packet 2]
Time wasted: 1 roundtrip (RTT) typically 50-100ms

For 10% loss:
  - Average latency increases 50-100x
  - Throughput drops significantly
  - Predictable degradation (known problem)
```

## Congestion Control: TCP's Response

TCP automatically detects loss and reduces sending rate:

```
Congestion window (cwnd): How many bytes to send before waiting for ack

No loss:
  cwnd = 100KB
  Send 100KB, get ack, increase cwnd
  cwnd = 110KB (growth)

Packet loss:
  Send 100KB
  Timeout (no ack)
  Decrease cwnd to 50KB
  Retry with smaller window

Result:
  Senders back off automatically
  Network gets less congestion
  Equilibrium reached
```

## Real-World: Trading Systems & Congestion

Trading requires predictable latency. Congestion = disaster.

```
Normal: Latency = 100 microseconds
Congestion: Latency = 100 milliseconds (1000x worse)

Stock trade happens at microsecond speed. If latency spikes:
  - Order arrives late
  - Price moved
  - Lost money
  
Prevention:
  - Dedicated network (not shared with others)
  - No congestion (bandwidth > peak traffic)
  - Monitor for drops (alert immediately)
  - Failover to backup network
```

## Detecting Congestion & Packet Loss

### Method 1: Latency Analysis

```
Baseline P99 latency: 50ms
Spike: P99 = 200ms

In congestion:
  Latency increases (packets waiting in queue)
  Variance increases (some packets hit congestion, some don't)

Alert: If P99 > baseline * 2x for 1 minute
```

### Method 2: Monitor Packet Loss

```bash
# On Linux
netstat -s | grep "segments retransmitted"

# Or using tcpdump
tcpdump -i eth0 'tcp[tcpflags] & tcp-ack != 0'

# High retransmit count = high loss
```

### Method 3: Throughput vs Latency

```
Without loss:
  Latency = 100ms, Throughput = 10,000 req/sec

With 1% loss:
  Latency = 1000ms (10x), Throughput = 100 req/sec (100x worse)
  
This dramatic drop is the signal something is wrong
```

## Solutions to Congestion

### Solution 1: More Bandwidth

```
Network link: 10 Gbps
Peak traffic: 9 Gbps
Margin: 10%

Upgrade: Network link to 100 Gbps
Peak traffic: 9 Gbps
Margin: 99%
Cost: $100K/month for dedicated bandwidth
```

Best but most expensive.

### Solution 2: Reduce Traffic

```
If spike is from one service:
  - Rate limit that service
  - Shed low-priority traffic
  - Redirect some traffic to backup path

Example: During market open, reduce logging/analytics
  Saves bandwidth for trading
```

### Solution 3: Adaptive Algorithms

```
Detect congestion (high latency):
  - Reduce batch size
  - Increase time between requests
  - Use smaller payloads
  - Compress data

This gives network time to clear
```

### Solution 4: Redundancy

```
Two network paths (mesh):
  Path A: NY → Chicago (primary)
  Path B: NY → Dallas → Chicago (backup)

If Path A congested:
  Failover to Path B
  Latency stays predictable
```

## Interview Pattern: Latency Spike Analysis

```
Q: "Your latency spiked 10x during market open.
   Recovered after 30 minutes. What happened?"

Weak answer:
  "Traffic was high"
  (❌ Doesn't explain recovery)

Strong answer:
  "Sounds like network congestion:
  
  1. Timeline:
     - 9:30am (market open): 10K -> 100K requests/sec
     - Latency: 100ms -> 1000ms (10x spike)
     - Retransmissions detected
     - 10:00am: Traffic dropped back to normal
     - Latency recovered to 100ms
  
  2. Root cause:
     - Network capacity = 50 Gbps
     - Peak traffic = 55 Gbps (5% oversubscribed)
     - Packets dropped
     - TCP backed off
     - Cascading failure: slower processing = more queuing
  
  3. Why did it recover?
     - At 10am, intraday volatility spike passed
     - Traffic returned to normal
     - Network cleared
     - No longer congested
  
  4. Why didn't monitoring catch it?
     - No alert on 'retransmits > threshold'
     - Latency alert was 2000ms (too high)
     - Should have alerted at 300ms
  
  5. Fixes:
     a) Short term: Alert on latency > 300ms
        Catch spike earlier
     
     b) Medium term: 
        - Reduce message size (compress)
        - Batch less aggressively (lower peak)
        - Route non-critical traffic elsewhere
     
     c) Long term:
        - Increase network capacity (60 Gbps)
        - Use redundant paths
        - Dedicated network for trading only
  
  6. Validation:
     - Measure before/after
     - Run load test (hit 100K req/sec)
     - Verify latency stays <300ms
     - Monitor over next market open
  
  Cost of congestion: Estimated $10M+ in missed trades
  Cost of fix: $1M (new network)
  Worth it."

Why this signals good judgment:
  - You understood congestion causes latency spike
  - You knew why it recovered (traffic dropped)
  - You had multi-level fixes (alert, optimize, capacity)
  - You understood cost-benefit
  - You'd monitor to prevent next time
```

## Checklist: Congestion Management

- [ ] Monitor latency percentiles (P99 baseline)
- [ ] Alert if P99 > baseline * 2x
- [ ] Monitor packet retransmits (netstat, tcpdump)
- [ ] Have alert on retransmit rate
- [ ] Capacity plan (bandwidth > peak traffic * 2x safety margin)
- [ ] Test failover paths (redundancy works?)
- [ ] Throttle/shed traffic under load (backpressure)

## What This Signals

- You've handled high-traffic spikes
- You understand network bottlenecks (not just CPU/memory)
- You think about cascading failures (congestion cascades)
- You monitor for predictable latency (critical for trading/finance)
