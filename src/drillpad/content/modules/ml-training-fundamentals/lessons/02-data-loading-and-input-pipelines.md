# Data Loading & Input Pipelines

## Throughput Bottleneck

```
Training loop:
  for batch in data_loader:
    predictions = model(batch)
    loss = compute_loss(predictions, batch.labels)
    loss.backward()
    optimizer.step()
    
Timing:
  ├─ Load batch: 100ms (slow!)
  ├─ GPU compute: 50ms (fast)
  └─ Total: 150ms (GPU idle 2/3 of time, bad!)

GPU utilization: 33% (wasted!)

Solution: prefetch + async loading
  ├─ While GPU computes batch N
  ├─ Load batch N+1 (CPU+SSD)
  └─ By time GPU finishes: next batch ready
```

## Prefetching & Caching

```
Single-threaded (slow):
  Load batch 1 → compute → load batch 2 → compute → ...
  GPU idle during load

Prefetch (async):
  Thread 1: load batches in parallel (N, N+1, N+2)
  Main: compute batch N
  While computing: N+1 already loaded
  
  Cost: small memory for queue (10-20 batches)
  Benefit: GPU never idles

Caching:
  ├─ Training runs: 10 epochs
  ├─ Same data loaded 10x
  ├─ Cache in RAM if size < available RAM
  ├─ Example: 100GB dataset, 256GB RAM → cache all
  └─ Benefit: 10x speedup (load once, reuse)
```

## Sampling & Shuffling

```
Without shuffle:
  ├─ Epoch 1: load class A, A, A, B, B, B
  ├─ Model learns: see A early, B late
  ├─ Gradient biased (early samples dominate)
  └─ Convergence slow

With shuffle:
  ├─ Epoch 1: random order (mix A and B)
  ├─ Model sees variety each batch
  ├─ Gradients less biased
  └─ Faster convergence

Implementation:
  ├─ In-memory shuffle: load all, shuffle (slow for large data)
  ├─ Streaming shuffle: rolling buffer (standard)
  │  └─ Buffer 10K samples, randomly pick batch
  └─ Cost: negligible
```

## Resume from Checkpoint

```
Problem: training for 1 week, crash at hour 150
  ├─ Restart: where in data are we?
  ├─ If restart from beginning: 150 wasted hours
  └─ Solution: checkpoint the data state

Checkpointing:
  1. Every N steps: save model weights + optimizer state + batch_index
  2. On resume:
     ├─ Load model + optimizer
     ├─ Skip to batch_index in data
     ├─ Resume training
     └─ Time lost: only failed batch
  
  Implementation:
    ├─ torch.save({model, optimizer, batch_idx})
    ├─ Resume: fast-forward data to batch_idx
    └─ DataLoader has sampler state (seed, ordering)
```

---

## Interview Checklist

- [ ] Prefetching: load next batch while GPU computes
- [ ] Shuffle: randomize order, reduce gradient bias
- [ ] Caching: in-memory for small datasets
- [ ] Batch size: large as GPU memory allows
- [ ] Checkpointing: save data state for resume

## Common Wrong Answers

- ❌ "Load data synchronously" — GPU idles, throughput halved
- ❌ "No shuffle" — biased gradients, slow convergence
- ❌ "No checkpoint" — data offset lost on crash
