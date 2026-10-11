# Fault Tolerance & Idempotency - Building Reliable Pipelines

## Exactly-Once for Data Pipelines

Problem: Task fails mid-way, gets retried

```
Task: Load features to warehouse
- Read 100M rows from S3 ✓
- Transform (30 min) ✓
- Write to Snowflake:
  - First 50M rows ✓
  - Crashes (network error)
  - Restart: Retry task
  
If not idempotent:
  - Re-read S3 (already cached, OK)
  - Re-transform (OK, same 100M rows)
  - Write again: First 50M rows get duplicated
  - Table now has 100M + 50M = 150M rows (WRONG)

If idempotent:
  - Use UPSERT (insert or replace by key)
  - Or: delete old data, write fresh
  - Result: Table has 100M rows (CORRECT)
```

## Making Tasks Idempotent

```
Non-idempotent (DON'T DO):
  INSERT INTO events_processed SELECT * FROM raw_events;
  (on retry: duplicate data)

Idempotent option 1: UPSERT
  MERGE INTO events_processed AS target
  USING raw_events AS source
  ON target.event_id = source.event_id
  WHEN MATCHED THEN UPDATE ...
  WHEN NOT MATCHED THEN INSERT ...;

Idempotent option 2: Overwrite
  CREATE TABLE events_processed_tmp AS SELECT * FROM raw_events;
  DROP TABLE events_processed;
  RENAME TABLE events_processed_tmp TO events_processed;
  (atomic swap)

Idempotent option 3: Checkpoint
  Process rows 0-1000000, save offset
  On crash, resume from offset (already processed rows skip)
```

## Retry Strategy

```
Transient failures (network, timeout): Retry
Permanent failures (bad data, schema mismatch): Don't retry

Airflow config:
  task.retries = 3
  task.retry_delay = 5 minutes (exponential)
  task.retry_delay_exp_base = 2
  
  Retries at:
    T=0 (fail)
    T=5 (fail)
    T=15 (fail)
    T=45 (fail)
    Task marked failed after 4th attempt
```

## Recovery and Checkpointing

```
Streaming-like recovery (Spark):
  Task processes 100M rows in batches of 1M
  After each batch: Save offset to database
  
  If crash at 45M processed:
    Restart from offset 45M
    Process 45-100M (55M rows)
    Total: 100M (no re-processing)

For data warehouses:
  Similar concept: Partition by date, process day-by-day
  If day 5 fails, re-run day 5 only
  (earlier days already complete)
```

## Interview Pattern: Reliability

```
Q: "Your pipeline processes 100M rows/day. Crashes 1% of the time.
   How do you ensure data is correct?"

Strong answer:
  "Idempotent + checkpoint strategy:
  
  1. Make tasks idempotent (UPSERT, not INSERT)
  2. Checkpointing: Save progress every 1M rows
  3. On crash: Resume from checkpoint (not re-process)
  4. Testing: Run on small sample first (1K rows)
  5. Validation: Check row count before/after
  
  Expected: 0 duplicates, 0 data loss, 100% completeness"
```

## What This Signals

- You understand failure is inevitable (design for it)
- You make tasks safe to retry (idempotent)
- You have monitoring (catch silent failures)
