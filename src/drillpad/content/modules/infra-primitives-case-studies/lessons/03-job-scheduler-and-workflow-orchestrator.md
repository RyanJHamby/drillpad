# Infrastructure Primitive: Job Scheduler & Workflow Orchestrator

## Firm Archetype: Airflow, Temporal, Kubernetes, Nomad, Luigi

**Problem:** Schedule N jobs across M machines. Handle failures (retry, backoff), dependencies (DAGs), exactly-once execution, recovery after crash.

**Why hard:** Partial failures (some jobs fail, others succeed), distributed consensus (which machine runs job?), state recovery (restart from failure point).

---

## Job Scheduling Basics

### Centralized Scheduler (Master-Worker)

```
Master: job scheduler
Workers: execute jobs

Job: "Process logs for 2025-01-01"
  ├─ Status: pending → queued → running → completed
  ├─ Worker: assigned to run job
  └─ Retry: if failed, retry up to 3x

Queue:
  Jobs waiting: [job_1, job_2, job_3]
  
  Master loop:
    1. Poll queue for jobs
    2. Pick next job (by priority)
    3. Assign to idle worker
    4. Monitor: heartbeat from worker
    5. If worker dies: requeue job

Worker:
  ├─ Registration: "I'm ready, can take 4 jobs"
  ├─ Heartbeat: every 10 sec ("still alive")
  ├─ Fetch job: GET /job/next
  ├─ Execute: run subprocess
  ├─ Report: POST /job/{id}/status {state: "completed"}
  └─ Next job

Database:
  jobs table:
    ├─ job_id
    ├─ status: pending | queued | running | failed | completed
    ├─ assigned_worker
    ├─ attempts: 0-3
    ├─ created_at
    ├─ started_at
    ├─ completed_at
    └─ error_message

Problem: master bottleneck
  ├─ 1000 workers × 10 sec heartbeat = 100 heartbeats/sec
  ├─ 100 job assignments/sec
  ├─ Total: 200 ops/sec (manageable, but scaling issue)
```

---

## DAGs (Directed Acyclic Graphs) & Dependencies

```
Workflow: Process logs → Group by date → Aggregate → Email

Dependency graph:
  
  [Process logs]
        |
  [Group by date]
        |
  [Aggregate]
        |
  [Email report]

DAG representation:
  {
    "tasks": {
      "process": {...},
      "group": {...},
      "aggregate": {...},
      "email": {...}
    },
    "dependencies": {
      "group": ["process"],
      "aggregate": ["group"],
      "email": ["aggregate"]
    }
  }

Execution:
  1. Mark tasks: status = pending
  2. Find ready tasks: all dependencies completed
  3. Execute ready tasks in parallel
  4. On completion: mark dependent tasks ready
  5. Repeat until all tasks done

Parallelism:
  
  [Task A] [Task B]  (independent, run in parallel)
       \     /
      [Task C]       (wait for both)
           |
      [Task D]

Timeline:
  A, B: 0-10 min (parallel)
  C: 10-20 min (after A, B)
  D: 20-30 min (after C)
  Total: 30 min (not 10+10+10+10=40)
```

---

## Exactly-Once Semantics

### Problem: Duplicate Execution

```
Scenario: Job "process_log_jan_1" runs on worker_A

1. Worker A executes job, writes results to database
2. Worker A: sends "completed" to master
3. Network fails before ACK received
4. Master: doesn't receive ACK, times out after 30 sec
5. Master: requeues job
6. Worker B: picks up job, executes again
7. Result: data processed twice (duplicates in database)
```

### Solution 1: Idempotent Operations

```
Idempotent operation:
  ├─ f(x) = f(f(x))
  └─ Safe to apply multiple times

Example:
  Operation: "Set user status = 'active'"
  
  First run: user status = 'inactive' → 'active' ✓
  Retry: user status = 'active' → 'active' ✓ (no change)
  
  Result: idempotent, safe to retry

Counter-example (NOT idempotent):
  Operation: "Increment counter by 1"
  
  First run: counter = 0 → 1 ✓
  Retry: counter = 1 → 2 ✗ (wrong result)
  
  Result: NOT idempotent, duplicate execution bad
```

### Solution 2: Deduplication (Idempotency Key)

```
Idempotency key: UUID assigned to job once

Job:
  {
    "job_id": "process_jan_1",
    "idempotency_key": "uuid_abc123",
    "status": "pending"
  }

Database:
  completed_jobs:
    {
      "idempotency_key": "uuid_abc123",
      "result": {...},
      "completed_at": 2025-01-01T10:30:00Z
    }

Execution:
  1. Worker picks up job
  2. Check: does idempotency_key exist in completed_jobs?
  3. If yes: job already ran, return cached result
  4. If no: execute, write to completed_jobs with idempotency_key
  
  Retry:
    ├─ Master: requeue job (new attempt)
    ├─ Worker: check idempotency_key → found
    ├─ Return cached result (no re-execution)
    └─ Effect: same result, no duplicate work

Benefit:
  ├─ Safe for non-idempotent operations
  ├─ Automatic deduplication
  └─ Transparent to job logic
```

---

## Failure Recovery & Checkpointing

### Resumable Jobs (Checkpointing)

```
Long job: process 1B rows (takes 2 hours)

Without checkpoint:
  ├─ Crash at 1:50 (99 minutes in)
  ├─ Restart: begins from row 1
  ├─ Lost: 99 minutes of work
  └─ Total: 2 + 2 = 4 hours

With checkpoint:
  ├─ Every 10 minutes: save progress
  ├─ Checkpoint 1: "processed rows 1-100M, offset=100M"
  ├─ Checkpoint 2: "processed rows 100M-200M, offset=200M"
  ├─ Crash at 1:50 (checkpoint 9 = offset 900M)
  ├─ Restart: begin from offset 900M
  ├─ Resume: process rows 900M-1B only
  └─ Lost: 10 minutes of work (not 99)

Checkpoint structure:
  {
    "job_id": "process_1b",
    "offset": 900000000,
    "timestamp": 2025-01-01T10:40:00Z,
    "state": {
      "rows_processed": 900000000,
      "rows_failed": 123,
      "last_row_id": 900000001
    }
  }

Recovery:
  ├─ Fetch latest checkpoint
  ├─ Resume from offset
  ├─ Total time: 2:10 (not 2:00 due to 10-min gap)
```

### Backoff & Retry Strategy

```
Retry policy:

Simple retry:
  ├─ Attempt 1: fail
  ├─ Attempt 2 (immediately): fail
  ├─ Attempt 3: fail
  ├─ Total attempts: 3
  ├─ Time: seconds (if fast failures)
  └─ Problem: no delay, hammer same server

Exponential backoff:
  ├─ Attempt 1: fail, wait 1 sec
  ├─ Attempt 2: fail, wait 2 sec
  ├─ Attempt 3: fail, wait 4 sec
  ├─ Attempt 4: fail, wait 8 sec (stop)
  ├─ Total time: 1 + 2 + 4 + 8 = 15 sec
  └─ Benefit: server recovers, later attempts likely succeed

Jitter (randomization):
  ├─ All workers retry with same backoff → thundering herd
  ├─ Solution: add random jitter
  ├─ Backoff: 2^attempt + random(0, 1 sec)
  └─ Spreads retries over time

Configuration:
  {
    "max_attempts": 5,
    "initial_delay": 1,
    "max_delay": 300,  # cap at 5 minutes
    "backoff_factor": 2,
    "jitter": true
  }
```

---

## Scale Calculation

```
1M jobs/day
Average duration: 10 minutes
Concurrency: 100,000 running jobs

Workers needed:
  ├─ 100,000 concurrent
  ├─ Each worker: 1 job at a time
  └─ Count: 100,000 workers (high!)

Optimization: parallelism per worker
  ├─ 4 jobs/worker (if jobs use <25% CPU)
  ├─ Workers: 100,000 / 4 = 25,000
  └─ More realistic

Job queue (Kafka/RabbitMQ):
  ├─ 1M jobs/day = 11.6 jobs/sec
  ├─ Partition: 100 partitions (10 jobs/sec per partition)
  ├─ Storage: 1M * 1 KB = 1 GB/day
  └─ Retention: 7 days = 7 GB

Scheduler (Master):
  ├─ Heartbeats: 25,000 workers * 1/10 sec = 2,500 hb/sec
  ├─ Job assignments: 11.6 jobs/sec
  ├─ Polling: 100 job completions/sec (10 min avg)
  ├─ Total: 2,600 ops/sec (easily handled by single master)
  └─ Redundancy: 3-way replication with consensus
```

---

## Failure Modes

### Worker Crash

```
Scenario: Worker A dies

Detection:
  ├─ Heartbeat: no response for 30 sec
  ├─ Master: mark A as dead
  └─ Jobs on A: status = running → requeue

Recovery:
  ├─ Requeue jobs (preserve idempotency_key for dedup)
  ├─ Assign to alive worker
  ├─ Result: job completes (possibly with checkpoint resume)

Timeline:
  ├─ 0 sec: Worker A dies
  ├─ 30 sec: Master detects
  ├─ 31 sec: Master requeues
  ├─ 32 sec: Another worker picks up
  ├─ Total downtime: 32 sec (acceptable)
```

### Master Crash

```
Scenario: Master dies, loses scheduler state

Problem:
  ├─ Running jobs: unknown (no one to monitor)
  ├─ Queue: partially lost
  ├─ New jobs: not scheduled

Prevention:
  ├─ Master replication: 3 masters with consensus
  ├─ On master crash: another takes over
  ├─ State: replicated via etcd/Zookeeper
  ├─ Recovery: new master reads state, resumes

State to replicate:
  ├─ Job queue: Kafka (durable, separate)
  ├─ Running jobs: etcd (who's running where?)
  ├─ Checkpoints: database (resumable state)
  └─ Result: recovery ~1 sec (failover time)
```

### Cascading Failure (Thundering Herd)

```
Scenario: DB goes down (all jobs that write data now fail)

Naive:
  ├─ 100,000 jobs fail simultaneously
  ├─ All retry immediately
  ├─ Retry storm: 100,000 * 3 attempts = 300,000 requests
  ├─ DB still overloaded
  └─ Cascading failure (retry queue fills, no progress)

Prevention: Circuit breaker + backoff
  ├─ After 10% job failure rate: open circuit
  ├─ New jobs: queued (not assigned)
  ├─ Backoff: wait 5 min before assigning more
  ├─ Gradual recovery: ramp up jobs, check DB health
  └─ Result: DB recovers gracefully, jobs don't retry endlessly
```

---

## Code Example (Simple Job Scheduler)

```python
import time
import uuid
import heapq
from dataclasses import dataclass
from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Job:
    job_id: str
    idempotency_key: str
    status: JobStatus
    dependencies: list  # job_ids
    attempts: int = 0
    max_attempts: int = 3
    backoff_delay: int = 1  # seconds
    assigned_worker: str = None
    created_at: float = None
    
    def __init__(self, job_id, dependencies=None):
        self.job_id = job_id
        self.idempotency_key = str(uuid.uuid4())
        self.status = JobStatus.PENDING
        self.dependencies = dependencies or []
        self.attempts = 0
        self.max_attempts = 3
        self.backoff_delay = 1
        self.created_at = time.time()

class JobScheduler:
    def __init__(self):
        self.jobs = {}  # job_id → Job
        self.queue = []  # priority queue: [(priority, job_id)]
        self.workers = {}  # worker_id → {status, last_heartbeat}
        self.completed = {}  # idempotency_key → result
    
    def submit_job(self, job_id, dependencies=None):
        """Submit job to scheduler."""
        job = Job(job_id, dependencies)
        self.jobs[job_id] = job
        self._update_job_status(job_id, JobStatus.PENDING)
        return job
    
    def _update_job_status(self, job_id, status):
        """Update job status and queue if ready."""
        job = self.jobs[job_id]
        job.status = status
        
        if status == JobStatus.PENDING:
            # Check if dependencies met
            if all(self.jobs[dep].status == JobStatus.COMPLETED 
                   for dep in job.dependencies):
                self._update_job_status(job_id, JobStatus.QUEUED)
        
        elif status == JobStatus.QUEUED:
            # Add to queue (priority = creation time, FIFO)
            priority = (job.created_at, job_id)
            heapq.heappush(self.queue, priority)
        
        elif status == JobStatus.COMPLETED:
            # Cascade: mark dependent jobs ready
            for other_id, other_job in self.jobs.items():
                if job_id in other_job.dependencies:
                    if other_job.status == JobStatus.PENDING:
                        self._update_job_status(other_id, JobStatus.QUEUED)
    
    def fetch_job(self, worker_id):
        """Worker fetches next job."""
        self.workers[worker_id] = {
            'status': 'idle',
            'last_heartbeat': time.time()
        }
        
        while self.queue:
            priority, job_id = heapq.heappop(self.queue)
            job = self.jobs[job_id]
            
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.RUNNING
                job.assigned_worker = worker_id
                job.attempts += 1
                return job
        
        return None
    
    def complete_job(self, job_id, result=None):
        """Job completed successfully."""
        job = self.jobs[job_id]
        
        # Store result for deduplication
        self.completed[job.idempotency_key] = {
            'job_id': job_id,
            'result': result,
            'completed_at': time.time()
        }
        
        self._update_job_status(job_id, JobStatus.COMPLETED)
    
    def fail_job(self, job_id):
        """Job failed, retry or mark failed."""
        job = self.jobs[job_id]
        
        if job.attempts < job.max_attempts:
            # Retry with backoff
            delay = min(2 ** job.attempts, 300)  # Exponential backoff, cap at 5 min
            print(f"Job {job_id}: retry in {delay} sec")
            
            # In practice: schedule retry at later time
            # For now: requeue
            self._update_job_status(job_id, JobStatus.QUEUED)
        else:
            # Max attempts reached
            self._update_job_status(job_id, JobStatus.FAILED)
            print(f"Job {job_id}: failed after {job.max_attempts} attempts")
```

---

## Interview Checklist

- [ ] Master-worker architecture (scheduler + workers)
- [ ] DAG execution (topological sort, parallelism)
- [ ] Exactly-once: idempotency + deduplication
- [ ] Checkpointing (resumable jobs)
- [ ] Retry strategy (exponential backoff + jitter)
- [ ] Failure modes: worker crash, master crash, cascading
- [ ] Scale: 1M jobs/day, 100K concurrent
- [ ] Queue: Kafka/RabbitMQ for durability

## Common Wrong Answers

- ❌ "Process jobs immediately" — no retry on failure, fragile
- ❌ "No deduplication" — duplicate execution (non-idempotent issues)
- ❌ "Immediate retry" — thundering herd, no backoff
- ❌ "No checkpoints" — 2-hour jobs lose 1 hour 50 min on crash
- ❌ "Single master" — master crash = service down
- ❌ "No DAG support" — can't parallelize workflows
