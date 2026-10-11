# Distributed Training: Checkpointing and Failure Recovery

## Why This Interview Matters

Training large models is expensive. A 70B model training on 8x H100s costs ~$10,000 per day. If training crashes after 5 days, you lose $50,000. **Checkpointing is how you recover gracefully.**

This is critical for AI infrastructure, ML systems, and training roles. Interviewers will ask: "Your training crashes. Can you resume from checkpoint? How long does recovery take?"

**Core insight:** Without checkpoints, a 30-day training run that crashes on day 29 means start over. With checkpoints, resume from day 28 in hours.

---

## First Principle: Stateful Training and Failure

A distributed training run has state:

```
Training state:
  - Model weights (70B parameters)
  - Optimizer state (momentum, variance for each param)
  - Learning rate schedule position
  - Data loader position (which batch is next?)
  - Random number generator seed position
  - Gradient accumulation buffer
  
If process crashes:
  All state is lost.
  You restart from epoch 0, batch 0.
  30 days of training = wasted.
```

**Why checkpointing matters:**

```
Checkpoint frequency: Every 6 hours (or every N steps)

Day 1: Train 24 hours → checkpoint-001.pt
Day 2: Train 24 hours → checkpoint-002.pt
...
Day 29: Train 24 hours → checkpoint-028.pt
Day 30: Train 6 hours → training succeeds (or crashes)

If crash on day 30, hour 2:
  Resume from checkpoint-028.pt (last known good state)
  Retrain from day 29, hour 0 (not day 1, hour 0)
  Cost: 6 hours * $416/hour (8 GPU cost) ≈ $2,500
  vs. $10,000 * 29 days = $290,000 (full restart)
```

---

## What Goes Into a Checkpoint?

A complete checkpoint includes:

```
checkpoint.tar.gz contains:
├── model/
│   ├── weights.safetensors    # 70B params in 140GB (fp32) or 70GB (fp16)
│   ├── config.json             # Model architecture
│   └── vocab.json              # Tokenizer vocabulary
├── optimizer_state/
│   ├── adam_m.bin              # First moment (momentum) [same size as weights]
│   ├── adam_v.bin              # Second moment (variance) [same size as weights]
│   ├── step_count.json         # Global training step
│   └── lr_scale.json           # Learning rate schedule state
├── training/
│   ├── step.txt                # Current global step (e.g., 1,000,000)
│   ├── epoch.txt               # Current epoch
│   ├── batch_idx.txt           # Current batch within epoch
│   └── rng_state.pkl           # Random seed (for reproducibility)
├── data/
│   └── loader_state.pkl        # Data loader position (shuffling seed, batch pointer)
└── metadata.json
    ├── timestamp
    ├── training_loss (last 100 steps)
    ├── validation_loss
    └── hardware_info
```

**Size estimate:**
```
Model weights: 70B params * 2 bytes (fp16) = 140GB
Optimizer state: 70B * 2 bytes * 2 (m and v) = 280GB
Training state: ~1GB
Total checkpoint: ~420GB
```

**Storage implications:**
- Save every 6 hours: 4 checkpoints/day * 420GB = 1.68 TB/day
- Keep last 3 checkpoints: ~1.3 TB disk
- Cloud storage (S3): ~$0.02 per GB/month = ~$26/month per checkpoint

---

## Checkpointing Strategies

### Strategy 1: Synchronous Checkpoint (Stop-the-World)

```
Training loop:
  for step in range(num_steps):
    loss = forward_backward(batch)
    optimizer.step()
    
    if step % checkpoint_frequency == 0:
      # STOP all GPUs
      torch.distributed.barrier()  # Wait for all GPUs to sync
      
      # Save checkpoint (only GPU 0 writes)
      if rank == 0:
        save_checkpoint(step, model, optimizer, ...)
      
      torch.distributed.barrier()  # Wait for save to complete
```

**Pros:**
- Guarantees all state is consistent
- Recovery is straightforward (no replaying logs)

**Cons:**
- All GPUs idle during checkpoint save (8 GPUs × 10 min save = 80 GPU-minutes wasted)
- Checkpoint every 6 hours = 40 minutes overhead per day per checkpoint
- 4 checkpoints/day = ~3 hours wasted per day

**Throughput loss:**
```
Ideal training throughput: 1000 tokens/sec per GPU
Checkpoint overhead: 10 min per checkpoint, 4 checkpoints/day = 40 min/day
Wasted: 40 min * 1000 tokens/sec = 40,000,000 tokens
Cost: ~$40 (lost productivity)

Acceptable for long runs (30 days) but adds up.
```

### Strategy 2: Asynchronous Checkpoint

Save checkpoint while training continues:

```
Training loop:
  for step in range(num_steps):
    loss = forward_backward(batch)
    optimizer.step()
    
    if step % checkpoint_frequency == 0:
      # Copy state to CPU memory (fast, 1-2 sec)
      state_copy = copy_state_to_cpu(model, optimizer)
      
      # Spawn background thread to save to disk
      threading.Thread(target=save_to_disk, args=(state_copy,)).start()
      
      # Continue training (don't wait)
      continue
```

**Pros:**
- Training continues while saving (minimal idle time)
- Checkpoint overhead: ~1-2 seconds per checkpoint (only copy, not save)

**Cons:**
- If training crashes DURING checkpoint save, recovery is tricky
  - Have a stale checkpoint (safe to resume from)
  - Have a partial checkpoint (corrupted, don't use)
- Need to handle crash during save: keep previous checkpoint as backup

**Implementation:**
```python
class AsyncCheckpointer:
  def __init__(self):
    self.save_thread = None
    self.last_good_checkpoint = None
    
  def checkpoint(self, step, model, optimizer):
    # Copy state (fast)
    state_copy = {
      'model': copy.deepcopy(model.state_dict()),
      'optimizer': copy.deepcopy(optimizer.state_dict()),
      'step': step,
    }
    
    # If previous save is still running, wait (avoid concurrent writes)
    if self.save_thread and self.save_thread.is_alive():
      self.save_thread.join()  # Blocks, but previous checkpoint is done
    
    # Spawn async save
    self.save_thread = threading.Thread(
      target=self._save_to_disk,
      args=(step, state_copy)
    )
    self.save_thread.daemon = True
    self.save_thread.start()
    
  def _save_to_disk(self, step, state):
    path = f"checkpoint-{step}.pt"
    torch.save(state, path)
    self.last_good_checkpoint = path
```

---

## Distributed Checkpointing: FSDP vs Data Parallel

### Fully Sharded Data Parallel (FSDP)

Each GPU holds only a shard of weights/optimizer:

```
8 GPUs, 70B model:
  GPU 0: Model shard [0-8.75B], Optimizer state [0-8.75B]
  GPU 1: Model shard [8.75-17.5B], Optimizer state [8.75-17.5B]
  ...
  GPU 7: Model shard [61.25-70B], Optimizer state [61.25-70B]

Checkpoint:
  - Gather all shards (gather from GPU 0-7 to GPU 0)
  - Save to disk on GPU 0
  - Scatter shards back
```

**Checkpoint code:**
```python
from torch.distributed.fsdp import FSDP, FullyShardedDataParallel

def checkpoint_fsdp(step, model: FSDP, optimizer):
  # Gather: model.consolidate_state_dict() collects all shards
  state_dict = model.consolidate_state_dict()  # GPU 0 gets full state
  
  if rank == 0:
    torch.save({
      'model': state_dict,
      'optimizer': optimizer.state_dict(),
      'step': step,
    }, f'checkpoint-{step}.pt')
  
  # Scatter: FSDP automatically reshards after save
  torch.distributed.barrier()
```

**Cost:**
- Consolidation (gather): AllGather(140GB) = ~10 seconds
- Save to disk: ~10 minutes
- Scatter (redistribute shards): ~5 seconds
- Total: ~10 min 15 sec, mostly waiting for disk

### Data Parallel (DDP)

Each GPU has full model:

```
8 GPUs, 70B model:
  GPU 0: Full model (140GB in fp16)
  GPU 1: Full model (140GB in fp16)
  ...
  GPU 7: Full model (140GB in fp16)

Checkpoint:
  - Save from GPU 0 only (other GPUs already have copy)
```

**Checkpoint code:**
```python
from torch.nn.parallel import DataParallel

def checkpoint_ddp(step, model: DataParallel, optimizer):
  if rank == 0:
    torch.save({
      'model': model.module.state_dict(),
      'optimizer': optimizer.state_dict(),
      'step': step,
    }, f'checkpoint-{step}.pt')
  
  torch.distributed.barrier()  # Wait for save
```

**Cost:**
- Save from GPU 0: ~10 minutes (same as FSDP)
- No gather/scatter overhead

**Tradeoff:**
- DDP: Faster checkpoint (no gather), but each GPU has full model (higher memory)
- FSDP: Slower checkpoint (gather/scatter), but lower per-GPU memory

---

## Recovery from Checkpoint

### Resume Training Loop

```python
def train(args):
  model = create_model()
  optimizer = create_optimizer(model)
  start_step = 0
  
  # Try to load checkpoint
  if os.path.exists(args.checkpoint_path):
    print(f"Loading checkpoint from {args.checkpoint_path}")
    ckpt = torch.load(args.checkpoint_path, map_location='cpu')
    model.load_state_dict(ckpt['model'])
    optimizer.load_state_dict(ckpt['optimizer'])
    start_step = ckpt['step'] + 1
    print(f"Resuming from step {start_step}")
  
  # Resume training
  for step in range(start_step, num_steps):
    batch = next(data_loader)
    loss = forward_backward(batch)
    optimizer.step()
    
    if step % checkpoint_frequency == 0:
      save_checkpoint(step, model, optimizer)
```

**Cost of recovery:**
```
Resume from checkpoint (step 1,000,000):
  1. Load model weights: 70GB → GPU memory (5-10 min via PCIe)
  2. Load optimizer state: 280GB → GPU memory (15-20 min)
  3. Resume training: Continue from step 1,000,001
  
Total recovery time: ~20-30 minutes
Cost: 8 GPUs idle for 25 min = $7 (vs. $50,000 lost if no checkpoint)
```

---

## Failure Scenarios and Recovery

### Scenario A: OOM (Out of Memory) During Training

```
Training was going fine.
Step 1,000,000: Run out of memory (model weights + gradients > 80GB on one GPU)
Process crashes.

Recovery:
  1. Load last checkpoint: step 999,000
  2. Reduce batch size (to avoid OOM)
  3. Resume from step 999,001
  
Cost: 1000 steps lost (not 1,000,000 steps)
```

### Scenario B: Network Outage

```
GPU 0 loses connection to cluster.
All-Reduce (gradient synchronization) times out.
Training hangs for 5 minutes, then crashes.

Recovery:
  1. Load last checkpoint (step 998,000)
  2. Restart training (all GPUs rejoin)
  3. Resume from step 998,001
  
Cost: 2000 steps lost + 5 min network outage
```

### Scenario C: Disk Failure During Checkpoint

```
Checkpoint is being written.
Disk on GPU 0 fails mid-write.
Checkpoint file is corrupted.

Recovery:
  Without backup checkpoint:
    - Load checkpoint from step 998,000 (2000 steps lost)
  With backup checkpoint:
    - Keep last 2 checkpoints on different disks
    - Load step 999,000 if 1,000,000 is corrupted
    - Resume from step 999,001 (1000 steps lost)
```

**Mitigation:**
```python
def robust_checkpoint(step, model, optimizer):
  path_new = f"checkpoint-{step}.pt"
  path_backup = f"checkpoint-{step}.pt.tmp"
  
  # Save to temporary file first
  torch.save({'model': model.state_dict(), ...}, path_backup)
  
  # Verify file is valid (read it back)
  try:
    verify = torch.load(path_backup)
    assert verify['model'] is not None
  except Exception as e:
    print(f"Checkpoint write failed: {e}")
    return  # Don't overwrite previous checkpoint
  
  # Only then move to final path
  os.rename(path_backup, path_new)
```

---

## Reproducibility from Checkpoint

A key property: **Resume should produce same training trajectory (deterministic replay).**

```
Scenario: Resume from checkpoint step 1,000,000
  Expected: Step 1,000,001 produces SAME loss as in original run
  Actual: Different loss (can be 5-10% variance due to randomness)
  
Why?
  - Random seed position must match
  - Floating point rounding (accumulation order in AllReduce)
  - Hardware variance (different GPU scheduling)
```

**Making it reproducible:**

```python
# Save random state
def checkpoint(step, model, optimizer):
  torch.save({
    'model': model.state_dict(),
    'optimizer': optimizer.state_dict(),
    'step': step,
    'random_seed': torch.get_rng_state(),
    'cuda_seed': torch.cuda.get_rng_state_all(),
    'np_seed': np.random.get_state(),
  }, f'checkpoint-{step}.pt')

# Restore random state
def resume(checkpoint):
  torch.set_rng_state(checkpoint['random_seed'])
  torch.cuda.set_rng_state_all(checkpoint['cuda_seed'])
  np.random.set_state(checkpoint['np_seed'])
```

**Gotchas:**
- Data loader shuffling: If you shuffle by seed, replay same shuffling (deterministic)
- Gradient accumulation order: AllReduce order varies if GPUs are different order
- Acceptable variance: Loss can differ slightly; what matters is trend is preserved

---

## Interview Q&A

**Recall 1:** Why do you need checkpoints during training? Why not just restart from scratch if something crashes?

*Must-say:*
- Training is expensive (70B model: $10,000 per day).
- A 30-day training run loses $300,000 if restart from scratch.
- Checkpoints let you resume from last known state, losing only a few hours of work.

**Probe 1:** Where should you save checkpoints? Local disk, or network storage?

*Expected:*
- Ideal: Both (local disk for speed, network for durability).
- Local disk: Fast writes (5-10 min), but lost if GPU node crashes.
- Network storage (NFS, S3): Slow writes (30+ min), but survived node crash.
- Tradeoff: Save async to local, periodic sync to network.

**Probe 2:** You have 8 GPUs training a 70B model with FSDP. How often should you checkpoint?

*Expected:*
- Frequency depends on cost of restart vs. overhead of checkpointing.
- If crash every ~week (realistic), checkpoint every 6 hours = 28 checkpoints.
- If crash every ~day, checkpoint every 1 hour.
- Rule of thumb: Checkpoint every 1-6 hours (depends on stability of hardware).

**Numeric 1:** A 70B model with fp32 weights and Adam optimizer state. What's the total checkpoint size?

*Working:*
- Weights (fp32): 70B * 4 bytes = 280 GB
- Optimizer state (Adam m and v): 70B * 4 bytes * 2 = 560 GB
- Total: 840 GB
- With fp16 mixed precision: 140 GB (weights) + 280 GB (optimizer) = 420 GB

**Numeric 2:** Checkpoint saves to disk in 10 minutes. You checkpoint every 6 hours. What's the throughput overhead?

*Working:*
- Checkpoints per day: 24 hours / 6 hours = 4 checkpoints
- Time overhead: 4 * 10 min = 40 minutes per day
- Throughput loss: 40 min / 1440 min = 2.8%
- Cost: 2.8% of $10,000 = $280 per day

---

## Checklist: Robust Training Checkpointing

- [ ] **Save checkpoint synchronously before the training loop starts.** (Never skip the initial checkpoint.)
- [ ] **Checkpoint frequently enough that loss is acceptable.** (Every 1-6 hours, not every step.)
- [ ] **Save model weights, optimizer state, and training metadata.** (Don't save just weights.)
- [ ] **Save random seeds and data loader position.** (For reproducibility.)
- [ ] **Use asynchronous checkpoint if possible.** (Copy to CPU async, save in background thread.)
- [ ] **Verify checkpoint is valid before deleting previous one.** (Read it back, check file size.)
- [ ] **Keep at least 2 recent checkpoints.** (Protection against disk corruption.)
- [ ] **Test recovery before production runs.** (Verify resume from checkpoint works.)
- [ ] **Monitor checkpoint save time.** (Alert if save > 15 minutes, indicate hardware issue.)

### Common Wrong Answers

- "I'll save just the model weights." ← No, need optimizer state too (gradient history).
- "I'll checkpoint every step." ← Too slow, kills throughput.
- "I'll checkpoint synchronously and wait." ← Acceptable but slower; async is better.
- "I'll resume without restoring random seed." ← Prevents reproducibility, hard to debug.

---

## Story Card: Scaling Llama Training

**Context:** Training Llama 70B on 8x H100 cluster. Original plan: 30-day run.

**Incident (no checkpointing):**
```
Day 28: Training going smoothly.
Day 29: Gradient explosion (numerical instability).
Recovery: Restart from scratch (no checkpoint).
Cost: 28 * $10,000 = $280,000 lost. Plus 30 more days.

Post-mortem: Why no checkpoints?
  Answer: "Thought checkpointing was too slow."
```

**Post-incident (with checkpointing):**
```
Same gradient explosion on day 29.
Recovery: Resume from day 28 checkpoint.
Cost: 6 hours to resume + 2 hours to debug + adjust hyperparams = $1,000.
Plus 2 more days (reduced learning rate to avoid explosion).

Total cost: ~$2,000 (vs. $280,000).
Time to fix: 2 days (vs. 60 days).
```

**Lesson:** Checkpointing saves more than computation; it saves sanity.

---

## Further Study

- **PyTorch Distributed Training**: `torch.distributed.checkpoint`
- **Hugging Face Trainer**: Checkpointing in `transformers.Trainer`
- **DeepSpeed**: ZeRO-Checkpoint for efficient multi-GPU training
- **FSDP Documentation**: `torch.distributed.fsdp.FullyShardedDataParallel`
