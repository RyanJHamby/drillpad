# Quantization: INT8, INT4, Calibration, and Accuracy Loss

## FP32 to INT8: 4x Memory Reduction

```
Model parameters: 70B * 4 bytes (FP32) = 280 GB
Quantized INT8: 70B * 1 byte = 70 GB (4x reduction)

Trade-off: accuracy loss (usually 0.5–2% top-1 on ImageNet, varies for LLMs)

Process:
  1. Calibration: collect statistics (min, max, percentiles) of activations/weights
  2. Map: FP32 range to INT8 range via affine transform: int8 = round((fp32 - zero_point) / scale)
  3. Inference: run model in INT8, dequantize outputs as needed for downstream layers
```

---

## Per-Channel vs Per-Tensor Quantization

```
Per-tensor (simplest):
  Single scale/zero-point for entire weight matrix W [4096, 4096]
  One scale value, one zero-point value
  Accuracy: ±2% (coarse)

Per-channel:
  Each output channel gets its own scale
  For W [4096, 4096], 4096 scales (one per output dim)
  Accuracy: ±0.5% (better, but more metadata)
  
Per-group (middle ground):
  Weights grouped by 16 or 32, each group has a scale
  64 groups for 4096 output dims
  Accuracy: ±1% (good balance)
```

---

## INT4: Extreme Quantization

```
70B in INT4: 70B * 0.5 bytes = 35 GB (8x reduction from FP32)

Challenge: INT4 is 4 bits, info density is high
  FP32 can represent [1e-38, 1e38] (huge range)
  INT4 represents [-8, 7] (tiny range)
  
  Solution: group quantization + careful calibration
  Example (GPTQ): quantize 128 weights at a time, use optimal quantization points
  
Accuracy: 2–5% loss (noticeable, but acceptable for many tasks)
```

---

## Calibration and Clipping

```
Histogram of weights in a layer:
  Most weights near 0 (bell curve)
  Few outliers (tails)

Naive: use min/max
  clip_range = [min, max]
  Problem: 1–2 outlier weights expand the range 10x
  All other weights get coarse quantization
  
Better: use percentiles (e.g., 99.9th percentile)
  clip_range = [0.1th percentile, 99.9th percentile]
  Drop outliers, better utilize INT8 range
  Outliers quantize to max INT8 (acceptable error)
  
Trade-off: drop 0.2% of values for better precision on 99.8%
```

---

## Inference: Dequantization Cost

```
Forward pass with quantized weights:

  int8_weight = quantize(weight)  # done once, offline
  x_fp32 = input
  
  # Inference step:
  y_int32 = x_int8 @ int8_weight  # integer matmul (fast)
  y_fp32 = dequantize(y_int32)    # scale back to FP32
  y_fp32 = apply_activation(y_fp32)
  
Dequantize cost: for each output, multiply by scale + add zero-point
  Latency: ~10% additional for matrix-multiply layer (matmul is the hot path)
  
If you quantize after matmul (post-training quantization):
  y_fp32 = x_fp32 @ w_fp32
  y_int8 = quantize(y_fp32)       # another quantize step
  Trade: move quantize overhead to output (still ~10%)
```

---

## Accuracy Impact on LLMs

```
ResNet-50 (vision): 1–2% top-1 drop with INT8 (acceptable)
BERT (NLP): 0.5–1% drop (good)
GPT-3 (LLM): 2–5% perplexity increase (language fluency degrades slightly)

Why worse for LLMs?
  Long dependencies: error accumulates over 2K tokens
  Each token processed through 80 layers, each with quantization error
  Errors compound
  
Mitigation:
  Quantize only weights, not activations (reduces error)
  Mixed precision: keep key layers (attention) in FP16, quantize others
  Fine-tuning: run training for a few epochs with quantization to recover accuracy
```

---

## Q&A

**Recall 1:** Why does per-channel quantization have better accuracy than per-tensor?

*Answer:* Per-tensor uses one scale for all output dimensions. Channels with small weights get coarse quantization (wasted precision), channels with large weights overflow INT8. Per-channel lets each channel choose its own scale, using full INT8 range per channel.

**Numeric 1:** 70B model in FP32 (280 GB) vs INT8 (70 GB) vs INT4 (35 GB). Speedup on H100 memory bandwidth?

*Working:* 2 TB/s bandwidth. FP32: 280 GB / 2 TB/s = 140 ms. INT8: 70 GB / 2 TB/s = 35 ms (4x faster). INT4: 35 GB / 2 TB/s = 17.5 ms (8x faster, but need dequant cost).

**Probe 1:** You quantize a model to INT8, accuracy drops 2%. Do you accept it?

*Expected:* Depends on application. For translation (accuracy critical), 2% is bad. For search ranking (precision not critical), 2% is OK. For chatbots, test on real users (accuracy might be imperceptible).

