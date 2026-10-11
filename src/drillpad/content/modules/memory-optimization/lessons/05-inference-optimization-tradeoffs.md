# Inference Optimization Tradeoffs: Accuracy vs Latency vs Memory

## Optimization Matrix

```
              Memory  Latency  Accuracy  Complexity
Quantization: ↓↓↓     ↓        ↓↓        Low
Pruning:      ↓↓      ↓        ↓         Medium
LoRA:         ↑       ↓        ↑         Low
Distillation: ↓       ↓        ↓         High
Sparsity:     ↓↓      ~ (if no hw)  ↓  High
```

---

## Choosing a Strategy

**For edge deployment (e.g., phone):**
  INT4 quantization + 50% structured pruning → 4–8x model size reduction
  Accuracy: -3%, but acceptable for many tasks
  Latency: 50 ms → 10 ms
  Cost: low (offline)

**For server inference (high throughput):**
  KV-cache quantization (INT8, per-token scaling)
  +vLLM continuous batching
  Accuracy: -1%, negligible
  Latency: unchanged, throughput +2–3x
  Cost: medium (quantization aware training)

**For personalization (many LoRAs):**
  Keep base model FP16, add r=4 LoRA per task
  Accuracy: +0–2% (task-specific improvement)
  Latency: +3%
  Memory: flat (shared base)
  Cost: low per LoRA

