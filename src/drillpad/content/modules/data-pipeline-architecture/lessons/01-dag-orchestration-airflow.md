# DAG Orchestration - Tasks, Dependencies, Airflow Patterns

## Why DAGs?

ETL pipeline: Extract data → Transform → Load to warehouse

```
Naive: Run tasks sequentially, if any fails the whole pipeline fails

Better: DAG (Directed Acyclic Graph)
- Each task is a node
- Edges show dependencies
- Run independent tasks in parallel
- Skip failed tasks, retry only them
```

## DAG Example: Training Pipeline

```
Input: Raw user events

    extract_events      extract_user_features
           \                    /
            \                  /
             \ ________________/
                    |
             merge_features
                    |
            validate_schema
                    |
            materialize_features
                    |
            train_model
```

Each box is a task:
- `extract_events`: Query database (2 hours)
- `extract_user_features`: Look up features (1 hour)
- `merge_features`: Join them (30 min)
- `validate_schema`: Check data quality (5 min)
- `materialize_features`: Write to warehouse (1 hour)
- `train_model`: Run training (3 hours)

Total sequential: 2+1+0.5+0.05+1+3 = 7.55 hours
With DAG:
- `extract_events` and `extract_user_features` run in parallel (2 hours total)
- Then merge and validate (30 + 5 min = 35 min)
- Then materialize (1 hour)
- Then train (3 hours)
- Total: 2 + 0.58 + 1 + 3 = 6.58 hours (saves ~1 hour via parallelism)

## Idempotency: The Key Property

Task: `merge_features`

```
Run 1: Reads events_v1, features_v1 → writes merged_v1
Run 2: Crashes during write
Restart: Reads events_v1, features_v1 → writes merged_v1 (overwrites)

Result: Correct (same output both times)
This is idempotent.
```

Non-idempotent:
```
Task: Increment counter

Run 1: counter = 0 → counter = 1
Run 2: Crashes, restarts → counter = 1 → counter = 2

Result: Wrong (counter is 2, should be 1)
```

For data pipelines: Always make tasks idempotent
- Read same inputs → Write same outputs
- Don't append, overwrite
- Don't increment, set

## Airflow Architecture

```
Scheduler:
  - Reads DAG definition
  - Creates task instances
  - Decides which tasks to run
  - Pushes to executor queue

Executor:
  - LocalExecutor: Run on single machine (dev)
  - CeleryExecutor: Run on cluster (prod)
  - KubernetesExecutor: Run on K8s (cloud-native)

Workers:
  - Pick tasks from queue
  - Execute them (run Python, SQL, Spark, etc.)
  - Report status back to scheduler
```

## Interview Pattern: Pipeline Design

```
Q: "Design a daily ML training pipeline.
   Raw events: 100M/day. Must complete in 6 hours.
   How do you structure it?"

Weak answer:
  "Extract, transform, load, train. All sequential."
  (❌ 100M rows transform takes hours, training takes hours)

Strong answer:
  "DAG-based pipeline with parallelism:
  
  1. Extract phase (parallel):
     - extract_events (1 hour)
     - extract_user_features (1 hour)
     - extract_geography (30 min)
     
     → Run all three in parallel (1 hour wall-clock)
  
  2. Transform phase:
     - merge_all_features: join the three (30 min)
     - validate_schema: check (5 min)
     - deduplicate: remove duplicates (15 min)
     → Sequential, 50 min total
  
  3. Feature engineering:
     - compute_derived_features (Spark job on 100M rows)
     - 30 vCPU cluster, 1 hour
     
  4. Load:
     - materialize_to_warehouse (Parquet, 30 min)
  
  5. Training:
     - split_train_test (2 min)
     - train_model (2 hours on 8x GPU)
  
  6. Total timeline:
     Extract (parallel):   1h
     Transform:            50m
     Feature eng:          1h
     Load:                 30m
     Train:                2h
     Total:                5.27 hours ✓ Under 6h budget
  
  7. Fault tolerance:
     - Each task is idempotent (safe to retry)
     - If train_model fails, re-run it (don't redo extract)
     - Airflow retries automatically (configurable)
  
  8. Monitoring:
     - Alert if pipeline takes > 6 hours
     - Log each task's duration
     - Identify bottleneck (is it feature_eng? train?)
  
  9. Scaling:
     - If extract becomes bottleneck, shard by date range
     - If feature_eng is slow, increase Spark cluster size
     - Track cost per run (infrastructure + compute)"

Why this signals good judgment:
  - You understood parallelism (extract tasks independent)
  - You met the time budget (fit in 6 hours)
  - You made tasks idempotent (safe retries)
  - You had monitoring strategy (catch slowdowns)
```

## Checklist: Pipeline Design

- [ ] DAG with task dependencies (not all sequential)
- [ ] Parallelizable tasks identified
- [ ] Each task is idempotent (safe to retry)
- [ ] Failure handling (retry logic, dead-letter tasks)
- [ ] Monitoring (task duration, cost, data quality)
- [ ] Testing (do one day's pipeline work first)

## What This Signals

- You've built scalable data pipelines
- You understand DAG scheduling and parallelism
- You know idempotency is non-negotiable
- You think about observability (monitoring bottlenecks)
