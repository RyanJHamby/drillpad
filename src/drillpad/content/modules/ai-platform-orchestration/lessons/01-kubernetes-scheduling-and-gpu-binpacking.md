# Kubernetes Scheduling: Pod/Node Placement, GPU Binpacking, Gang Scheduling

## The Problem

You have a Kubernetes cluster with 8 GPU nodes. Each node has 8x H100 GPUs. You want to run a model that needs 4 GPUs on a single node (to avoid network overhead).

Naive Kubernetes default:
```
Pod 1: Requests 4 GPUs
  → K8s assigns GPU 0,1,2,3 on node-1
  
Pod 2: Requests 4 GPUs
  → K8s assigns GPU 4,5,6,7 on node-1 ✓ Still fits

Pod 3: Requests 4 GPUs
  → K8s looks for 4 free GPUs
  → Finds GPU 0,1 on node-1 (2) + GPU 0,1 on node-2 (2)
  → SPLITS ACROSS NODES ✗
  
Result: Pod 3 sees NVLink unavailable (cross-node), bandwidth limited
  Expected: 900 GB/s (NVLink within node)
  Actual: 50 GB/s (InfiniBand across nodes)
  Performance: 18x slower!
```

**Why this matters:** Kubernetes' default scheduler doesn't understand GPU topology. It treats each GPU as an independent resource. For AI workloads, you must bin-pack GPUs onto single nodes to enable NVLink.

---

## First Principles: K8s Scheduling Constraints

Standard Kubernetes scheduler:
- Sees CPU, memory as divisible resources
- Packs containers to minimize node count
- Doesn't understand GPU topology, NVLink vs PCIe vs InfiniBand

AI workload requirements:
- GPUs must be on same node (NVLink bandwidth critical)
- Model may need atomic allocation (all GPUs or fail)
- Some GPUs may prefer specific nodes (NUMA, network connectivity)

```
Problem: Scheduler must know topology

CPU scheduling:
  Pod wants 4 CPUs
  Scheduler: "Allocate from any CPUs that fit"
  CPUs are interchangeable (maybe NUMA penalty, but OK)

GPU scheduling:
  Pod wants 4 GPUs
  Scheduler: "Allocate 4 GPUs on SAME node, all with NVLink"
  GPUs are NOT interchangeable (topology matters)
```

---

## GPU Resource Scheduling

Kubernetes natively supports GPU requests:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: model-inference
spec:
  containers:
  - name: inference
    image: ai-model:latest
    resources:
      requests:
        nvidia.com/gpu: 4  # Request 4 GPUs
      limits:
        nvidia.com/gpu: 4
```

**How it works:**

```
1. Cluster has nodes with GPUs
   Node-1: 8x H100
   Node-2: 8x H100
   Node-3: 8x H100

2. Kubelet (node agent) reports available resources
   Node-1 reports: 8 nvidia.com/gpu available

3. Scheduler tries to place Pod
   Finds Node-1 has ≥4 GPUs
   Places Pod on Node-1

4. Kubelet allocates GPUs to container
   Allocates devices 0,1,2,3 to container
```

**Problem: No topology awareness**

```
Scheduler sees:
  Node-1: 8 GPUs (doesn't know they're in 2 groups of 4 on PCIe switches)
  Pod wants: 4 GPUs

Scheduler allocates: GPUs 0,1,2,3
But GPUs 0,1 and 2,3 are on different PCIe switches
  GPU 0-1 bandwidth: 900 GB/s (NVLink)
  GPU 2-3 bandwidth: 900 GB/s (NVLink)
  GPU 0-1 ↔ 2-3: 50 GB/s (InfiniBand crossing)
```

---

## GPU Topology Awareness (NVIDIA Device Plugin)

NVIDIA GPU device plugin adds topology labels to nodes:

```yaml
# Pod requests GPUs with topology hints
apiVersion: v1
kind: Pod
metadata:
  name: model-gpu-request
spec:
  containers:
  - name: inference
    resources:
      requests:
        nvidia.com/gpu: 4
  # Node affinity: prefer certain nodes
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: nvidia.com/gpu.count
            operator: Gt
            values: ["3"]  # At least 4 GPUs
```

**Diagram: GPU Topology on Node**

```
Node-1 (8x H100):

NVLink topology:
  PCIe Switch 0:
    GPU 0 ↔ GPU 1 (NVLink, 900 GB/s)
    GPU 2 ↔ GPU 3 (NVLink, 900 GB/s)
    GPU 0,2 ↔ GPU 1,3 (PCIe, 300 GB/s)

  PCIe Switch 1:
    GPU 4 ↔ GPU 5 (NVLink, 900 GB/s)
    GPU 6 ↔ GPU 7 (NVLink, 900 GB/s)

  Switches ↔ InfiniBand (50 GB/s)

Pod placement for 4-GPU model:
  Best: GPUs 0,1,2,3 (all on Switch 0, NVLink connected)
  Bad: GPUs 0,1,4,5 (two different switches, InfiniBand bottleneck)
```

---

## Gang Scheduling (Atomic Pod Scheduling)

Some workloads need ALL resources allocated atomically, or none at all:

```
Distributed training: 8 replicas, each needs 1 GPU
Kubernetes default: Schedule them one by one
  Replica 1: GPU-0 on node-1 ✓
  Replica 2: GPU-0 on node-2 ✓
  Replica 3: GPU-0 on node-3 ✓
  Replica 4: No GPUs available ✗
  
  Replica 4 sits in Pending state
  Training can't start (needs all 8 to form collective)
  GPUs 0-2 are idle, waiting for GPU 4

Gang scheduling solution:
  Submit 8 pods as a "gang"
  Scheduler: Either allocate ALL 8 or NONE
  Result: Either all start together, or all wait
```

**Implementation:** Coscheduling plugins (e.g., Apache YuniKorn, Karpenter)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: distributed-training
spec:
  serviceName: training
  replicas: 8
  template:
    spec:
      # Pod group for gang scheduling
      scheduling.incubator.k8s.io/group-name: training-job-1
      containers:
      - name: trainer
        resources:
          requests:
            nvidia.com/gpu: 1
```

---

## Bin-Packing Strategies

**Strategy 1: Least-Loaded Node First**

```
Scheduler: "Allocate to the node with most free GPUs"

Scenario: 3 nodes with 8 GPUs each
  Node-1: 8 free
  Node-2: 4 free
  Node-3: 2 free

Pod requests 4 GPUs:
  Allocate to Node-1 (most free)
  
Result:
  Node-1: 4 free
  Node-2: 4 free
  Node-3: 2 free
  
Next Pod requests 4 GPUs:
  Allocate to Node-1 or Node-2 (tied)
  Say Node-1
  
Result:
  Node-1: 0 free ✓ (consolidated)
  Node-2: 4 free
  Node-3: 2 free
```

**Strategy 2: Most-Loaded Node First (Consolidation)**

```
Scheduler: "Fill the most-loaded node first"

Same scenario:
  Node-1: 8 free
  Node-2: 4 free
  Node-3: 2 free

Pod requests 4 GPUs:
  Allocate to Node-2 (most loaded = least free)
  
Result:
  Node-1: 8 free (not touched)
  Node-2: 0 free ✓
  Node-3: 2 free
  
Node-1 becomes a "hot spare" (can be deprovisioned)
```

**Trade-off:** Consolidation saves on node count. Least-loaded spreads load (better for resilience).

---

## Failure Scenario: Pod Fragmentation

```
Cluster: 3 nodes, 8 GPUs each (24 total)

Pod A: 4 GPUs
  Allocated to Node-1 (GPUs 0-3)
  
Pod B: 4 GPUs
  Allocated to Node-1 (GPUs 4-7) ✓ Node-1 full

Pod C: 4 GPUs
  Allocated to Node-2 (GPUs 0-3)

Pod D: 4 GPUs
  Allocated to Node-2 (GPUs 4-7) ✓ Node-2 full

Pod E: 4 GPUs
  Allocated to Node-3 (GPUs 0-3)

Pod F: 4 GPUs
  Allocated to Node-3 (GPUs 4-7) ✓ Node-3 full

Now: Cluster is 100% full (24/24 GPUs allocated)

New Pod G needs 4 GPUs:
  Scheduler tries to allocate
  Checks Node-1: 0 free
  Checks Node-2: 0 free
  Checks Node-3: 0 free
  Result: Pod G stays Pending ✗

But: Pod A (4 GPUs) terminates
  Node-1: 4 GPUs free
  Pod G gets scheduled

Problem: If Pod G needs 8 GPUs (not 4):
  Even after Pod A terminates
  No single node has 8 free GPUs
  Pod G stays Pending (fragmented)
```

**Detection:** Monitor node utilization distribution

**Prevention:**
- Reserve capacity (don't pack to 100%)
- Bin-pack aggressively (fewer, fuller nodes)
- Monitor fragmentation metric (% of pods waiting for placement)

---

## Interview Pattern: GPU Scheduling Puzzle

```
Q: "You have 4 K8s nodes, 8 A100 GPUs each.
   You submit 16 pods, each requesting 4 GPUs.
   After scheduling, some pod is stuck in Pending.
   How could this happen if total capacity is 32 GPUs and demand is 16×4=64?
   (Wait, that doesn't add up... did you mean 16 pods total needing 64?)
   
   Let me re-ask: You submit 8 pods requesting 4 GPUs each.
   Total: 32 GPUs, exactly fits 4 nodes.
   But one pod is Pending. Why?"

Weak answer:
  "Maybe a node is down"
  (❌ Would see it in monitoring)
  
  Or: "GPU driver crashed"
  (❌ All 4 nodes can't crash)

Strong answer:
  "Scheduler fragmentation: GPUs are allocated but not bin-packed.
  
  Example:
    Node-1: Pod 1 (GPUs 0-3), Pod 2 (GPUs 4-7) → Full
    Node-2: Pod 3 (GPUs 0-3), Pod 4 (GPUs 4-7) → Full
    Node-3: Pod 5 (GPUs 0-3), 4 free GPUs
    Node-4: Pod 6 (GPUs 0-3), 4 free GPUs
    
    Pod 7 (needs 4): Can fit on Node-3 or Node-4 ✓
    Pod 8 (needs 4): Can fit on the remaining node ✓
    
  Wait, that works. Let me think of the actual failure case...
  
  Actually, this could happen if:
    1. Pod affinity rules prevent consolidation
       Pod A needs node-1, Pod B needs node-2 (forced spread)
    2. GPU topology mismatch
       Pod requests 4 GPUs but they must be on same NVLink group
       If nodes have non-homogeneous GPU placement, some pods can't fit
    3. NUMA constraints
       Pod requests 4 GPUs + memory from same NUMA node
       Not all allocations satisfy both constraints
  
  Most likely: Scheduler doesn't understand GPU topology
    Node-1: GPU 0,1 on NVLink group A; GPU 2,3 on NVLink group B
    Pod 7 needs: 4 GPUs on same NVLink group
    Scheduler allocated: GPU 0,2 (different groups)
    Application gets bad topology (cross-group is PCIe)
  
  Fix:
    1. Use GPU device plugin that understands topology
    2. Add pod affinity to keep pods on same node
    3. Implement gang scheduling (allocate 8 pods atomically)
    4. Preempt lower-priority pods to make room
"

Why this signals good judgment:
  - You understand K8s default scheduler limitations
  - You know GPU topology matters
  - You have multiple hypotheses and can test them
  - You know cluster invariants (total capacity) vs per-node limits
```

---

## Checklist: K8s GPU Scheduling

- [ ] GPU device plugin deployed (NVIDIA or AMD)
- [ ] Node labels include GPU count, type, topology
- [ ] Pod resource requests include nvidia.com/gpu
- [ ] Bin-packing strategy documented (least-loaded vs consolidation)
- [ ] Gang scheduling enabled (if doing distributed training)
- [ ] Pod affinity rules prevent cross-node splits (if needed)
- [ ] Fragmentation monitoring in place (% pods waiting)
- [ ] Capacity reserved (not scheduling to 100%)

## Common Wrong Answers

1. **"Kubernetes automatically understands GPU topology"**
   - No, you must add device plugin + topology labels

2. **"GPUs are interchangeable like CPUs"**
   - No, NVLink topology is critical
   - Cross-node is 18x slower

3. **"Just increase cluster size if pods are pending"**
   - Better: Fix fragmentation first (bin-pack better)

4. **"No need for gang scheduling"**
   - True for single-GPU pods
   - Multi-GPU distributed training needs it

5. **"Pod affinity will prevent fragmentation"**
   - Helps, but not automatic
   - Still need bin-packing strategy
