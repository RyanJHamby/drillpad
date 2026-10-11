# Schema Validation - Types, Constraints, Null Handling

## Why Schema Matters

```
Pipeline task: Load events to warehouse

Run 1 (success):
  Input: events table
    id (int), timestamp (datetime), customer_id (int), amount (float)
  All rows valid
  Load succeeds

Run 2 (failure):
  Same input schema
  But one row: id="abc" (string, not int)
  Load fails mid-way: "Type mismatch: expected int, got string"
  Data partially loaded (CORRUPTED)

With validation:
  Check schema before loading
  Reject row with id="abc"
  Alert: "1 invalid row detected"
  Option: Fix upstream or skip row
  Load succeeds with clean data
```

## Type Checking

```
Schema definition (Python):
  id: int (required)
  timestamp: datetime (required)
  customer_id: int (required)
  amount: float (≥ 0)
  notes: string (optional, max 256 chars)

Validation rules:
  ✓ id=1, timestamp="2025-01-15T10:30:00", customer_id=42, amount=99.50
  ✓ id=2, timestamp="2025-01-15T10:31:00", customer_id=43, amount=0.01, notes=""
  ✓ id=3, timestamp="2025-01-15T10:32:00", customer_id=44, amount=50.00, notes=NULL
  ✗ id="abc" (type mismatch)
  ✗ amount=-5.50 (negative)
  ✗ notes="x" * 300 (too long)
```

## Constraint Checking

```
Business constraints:
  - customer_id must exist in customers table
  - timestamp must be within last 30 days
  - amount must be > 0 (no free transactions)
  - status must be one of: pending, completed, failed

Validation:
  ✓ customer_id=42 (exists in DB)
  ✗ customer_id=999 (not in DB, FK violation)
  ✓ timestamp=2025-01-10 (within 30 days)
  ✗ timestamp=2024-01-01 (older than 30 days)
  ✓ status="completed"
  ✗ status="unknown" (not in allowed set)
```

## Null Handling

```
Null policy: Decide per column

  id: NOT NULL (required)
  timestamp: NOT NULL (required)
  customer_id: NOT NULL (required)
  amount: NOT NULL (required)
  notes: NULL OK (optional)
  discount_code: NULL OK (optional)

Validation:
  ✓ amount=50.00 (not null)
  ✗ amount=NULL (violates NOT NULL)
  ✓ notes=NULL (allowed)
  ✓ discount_code=NULL (allowed)
```

## Schema Evolution

```
Original schema (v1):
  id (int), timestamp (datetime), customer_id (int), amount (float)

New requirement: Track payment method

Schema v2:
  id (int), timestamp (datetime), customer_id (int), amount (float), 
  payment_method (string)

Problem: Old data has no payment_method column

Options:
  1. Backfill: Add default payment_method="unknown" to old rows
  2. Allow null: Mark payment_method as nullable
  3. Separate logic: Handle old vs new data differently

Best: Option 1 (backfill with sensible default)

Migration:
  ALTER TABLE events ADD COLUMN payment_method VARCHAR(32) DEFAULT 'unknown';
  
Old rows now have payment_method="unknown"
New rows have payment_method set correctly
All rows valid under v2 schema
```

## Interview Pattern: Validation

```
Q: "Your data pipeline loads 100M events/day.
   You discover 0.1% of rows have invalid customer_id.
   How do you handle it?"

Weak answer:
  "Skip them"
  (❌ How many? Where do they go? Any logging?)

Strong answer:
  "Comprehensive approach:
  
  1. Detect:
     - Schema validation on input (type, nulls)
     - Constraint check on customer_id (FK check)
     - Find rows with invalid customer_id
  
  2. Quantify:
     - 100M rows * 0.1% = 100K invalid rows
     - Log: 'Found 100K rows with invalid customer_id'
     - Investigate: Why? Data quality issue upstream?
  
  3. Handle:
     - Write invalid rows to dead-letter table
     - Main table: Skip them (clean load)
     - Dead-letter: Quarantine for investigation
     - Alert: 'Validation caught 100K rows'
  
  4. Investigate:
     - Sample dead-letter rows
     - Query events API logs: Why missing customer_id?
     - Is API returning bad data? Is upstream broken?
  
  5. Fix:
     - Option A: Fix upstream (API returns valid IDs)
     - Option B: Backfill missing customer_ids
     - Option C: Establish data quality SLA (< 0.01% invalid)
  
  6. Monitoring:
     - Track validation failure rate daily
     - Alert if > 0.1%
     - Prevent silent data corruption"

Why this signals good judgment:
  - You catch problems early (validation before load)
  - You don't silently drop data (investigate)
  - You have monitoring (catch next time)
  - You fix root cause, not symptom
```

## Checklist: Data Validation

- [ ] Schema defined (types, nulls, constraints)
- [ ] Validation rules enforced (type checks, FK checks, business logic)
- [ ] Invalid data handling (dead-letter, quarantine, or backfill)
- [ ] Monitoring (track failure rate, alert on anomalies)
- [ ] Testing (validate on sample data first)
- [ ] Documentation (schema versions, evolution strategy)

## What This Signals

- You prevent data corruption (validate early)
- You're systematic about data quality (not ad-hoc)
- You investigate, don't just skip (get to root cause)
- You think about the full pipeline (input → validation → output)
