# Communication vs Computation: PCIe, NVLink, Infiniband Bandwidth

## Roofline Model: Compute vs Bandwidth

Attainable GFLOPS = min(peak GFLOPS, bandwidth * arithmetic intensity)

```
Peak compute: 312 TFLOPS (A100)
Bandwidth: 2 TB/s (NVLink, intra-GPU memory)

Arithmetic intensity = FLOPs / bytes read-written

For matrix multiply y = x @ W:
  FLOPs: 2 * n * m * k (n=batch, m=k=hidden)
  Bytes: n*k + k*m + n*m (x, W, output, roughly)
  
  Typical: n=32, k=4096, m=4096
  FLOPs: 2 * 32 * 4096 * 4096 ≈ 1 billion
  Bytes: ~100 MB
  Intensity: 1B / 100M ≈ 10 FLOP/byte
  
  Attainable: min(312 TFLOPS, 2 TB/s * 10) = min(312, 20) TFLOPS = 20 TFLOPS
  Actual: 20 TFLOPS / 312 TFLOPS = 6% efficiency (memory-bound!)
```

---

## Network Bandwidth Tiers

```
PCIe 4.0: 32 GB/s
PCIe 5.0: 64 GB/s

NVLink 3 (A100/H100): 900 GB/s (intra-GPU memory bus)
NVLink 4 (future): 1.8 TB/s

Infiniband HDR: 200 GB/s (top-of-rack switch)
Infiniband NDR: 400 GB/s

Communication cost for AllReduce 1 GB on different networks:
  PCIe 4.0: 1 GB / 32 GB/s = 31 ms (ouch)
  NVLink: 1 GB / 900 GB/s = 1.1 ms
  Infiniband HDR: 1 GB / 200 GB/s = 5 ms
  
Tradeoff: NVLink is 30x faster than PCIe for same GPU pair.
```

---

## Communication-to-Computation Ratio

For a 70B model, forward pass latency:

```
Setup: 8 GPUs, tensor parallelism, AllGather after each layer (80 layers)

Computation:
  Per layer: 70B / 8 ≈ 9B parameters
  Prefill 2K tokens: ~2K * 9B FLOPs = 18T FLOPs
  At 312 TFLOPS: 18T / 312T ≈ 57 ms per layer
  Total: 80 * 57 ms ≈ 4.6 seconds

Communication (AllGather):
  Per layer: 4096 hidden * 2 (fp16) ≈ 8 KB (small!)
  But with 2K token batch: 4096 hidden * 2K tokens ≈ 16 MB per layer
  At 900 GB/s (NVLink): 16 MB / 900 GB/s ≈ 0.018 ms per AllGather
  Total: 80 * 0.018 ms ≈ 1.4 ms (negligible!)

Ratio: 1.4 ms communication / 4.6 s computation = 0.03% (good, compute-bound)

But! If using PCIe (32 GB/s instead of NVLink):
  16 MB / 32 GB/s ≈ 0.5 ms per AllGather
  Total: 80 * 0.5 ms = 40 ms
  Ratio: 40 ms / 4.6 s = 0.87% (still OK, but noticeable)
```

---

## Decoding: Different Bottleneck

Decode is memory-bound, communication matters more.

```
Decode 1 token (all 80 layers):
  Computation: 70B parameters * 1 token ≈ 70B FLOPs ≈ 0.22 ms
  Memory reads: 70B params * 2 bytes ≈ 140 GB reading
  At 900 GB/s: 140 GB / 900 GB/s ≈ 155 ms
  
  Ratio: 155 ms memory / 0.22 ms compute = 700x more time reading than computing

If 8-GPU TP, each GPU needs to AllGather outputs:
  AllGather: 4K hidden * 2 bytes ≈ 8 KB per token
  At 900 GB/s: 8 KB / 900 GB/s ≈ 9 μs (tiny)
  But latency matters (serialized): 8 KB latency ≈ 9 μs * 8 AllGathers = 72 μs (still tiny)

Communication is negligible; memory bandwidth to model parameters is the real bottleneck.

Solution: Quantization (reduce parameter size) or speculative decoding (generate multiple tokens in parallel to amortize memory cost).
```

---

## Q&A

**Recall 1:** What is arithmetic intensity? How does it relate to efficiency?

*Answer:* Arithmetic intensity = FLOPs / bytes moved. High intensity (> 10 FLOP/byte) is compute-bound. Low intensity (< 1) is memory-bound. Multiply by bandwidth to get attainable GFLOPS.

**Numeric 1:** A100 bandwidth 2 TB/s, matrix multiply with intensity 4 FLOP/byte. Peak GFLOPS 312. Attainable GFLOPS?

*Working:* min(312, 2000 * 4) = min(312, 8000) = 312 TFLOPS (compute-bound, good).

**Numeric 2:** PCIe 4.0 at 32 GB/s, need to AllGather 128 GB across 8 GPUs. Time?

*Working:* Ring AllReduce in 2 phases, each phase = 128 GB / 8 = 16 GB per link. 16 GB / 32 GB/s = 0.5 s per phase = 1 second total. (Very slow!)

**Probe 1:** You have 4 GPUs in one machine (NVLink 900 GB/s) and 4 GPUs in another (connected via 100 Gb Ethernet = 12.5 GB/s). How do you partition tensor/pipeline parallelism?

*Expected:* Tensor parallelism within each machine (NVLink, fast AllGather), data parallelism across machines (gradient averaging, less frequent communication). Never split tensor parallelism across slow network.

