# Lambda, S3, IAM: Design Implications

## Lambda Cold Starts

```
Execution time: init + code

Cold start (first execution):
  ├─ Load runtime: 100-500ms (Java worst)
  ├─ Load code: 10-100ms
  ├─ Execute: 10-100ms
  └─ Total: 200-700ms (slow!)

Warm start (reused):
  ├─ Skip init: container already loaded
  ├─ Execute only: 10-100ms
  └─ Fast!

Design implications:

Problem: API endpoint with Lambda
  ├─ User requests: 500ms init + 50ms compute = 550ms (slow)
  └─ Solution: keep warm

Solutions:
  ├─ Provisioned concurrency: always-on Lambda instances
  ├─ Cost: $0.015/hour per instance
  └─ Trade-off: pay for always-on vs cold-start latency

When to use Lambda:
  ├─ Async: background jobs (cold start OK)
  ├─ Low-latency: API -> use EC2/ECS, not Lambda
  └─ Example: SQS → Lambda for data processing (cold start OK)
```

## S3 Consistency

```
Strong consistency (Jan 2023):
  ├─ PUT new object: immediately visible
  ├─ GET object: returns latest version
  └─ DELETE: returns error if not found
  
Benefits:
  ├─ No race conditions
  ├─ Safe for critical data (configs, databases)
  └─ Default behavior (no configuration)

Previous: eventual consistency
  ├─ Write may not be immediately visible
  ├─ Retry needed
  └─ Legacy behavior (no longer default)

Design implications:

Config update:
  ├─ Write config.json to S3
  ├─ App reads config.json
  ├─ Guaranteed to see new version (strong consistency)
  └─ Safe (no eventual consistency issues)

Prefix sharding:
  ├─ Old advice: write to different prefixes to avoid throttling
  ├─ Reason: eventual consistency had throttling limits
  ├─ New: not needed (consistent hashing, no throttling)
  └─ Can write to same prefix freely
```

## IAM in Multi-Tenant Systems

```
Problem: customer_a should only access their data

Naive (bad):
  ├─ All customers get same IAM user
  ├─ customer_a can access customer_b's S3 bucket
  └─ Security breach!

Correct design:

Option 1: per-tenant IAM user
  ├─ Create IAM user per customer
  ├─ Grant permissions: s3:GetObject on bucket/customer_a/*
  ├─ Cost: 1 IAM user per customer (cheap, no quota issues)
  └─ Problem: managing 1M customers = 1M users

Option 2: policy templates
  ├─ Single IAM user with policy:
  │  {
  │    "Effect": "Allow",
  │    "Action": "s3:GetObject",
  │    "Resource": "arn:aws:s3:::bucket/${aws:username}/*"
  │  }
  ├─ Variable expansion: ${aws:username} = customer_a
  └─ Result: customer_a can only access customer_a/* prefix

Option 3: temporary credentials (STS)
  ├─ Generate temporary STS token for customer
  ├─ Policy: restricted to that customer's prefix
  ├─ TTL: 1 hour (automatic expiry)
  ├─ Cost: simple, no per-customer IAM users
  └─ Used by: AWS Cognito, cross-account access
```

## Design Example: Multi-Tenant SaaS

```
Architecture:
  ├─ Customer portal (API Gateway)
  ├─ Backend (Lambda)
  ├─ Storage (S3 with per-customer prefix)
  └─ Database (DynamoDB with customer_id as PK)

Flow:
  1. Customer logs in → Cognito
  2. Cognito issues STS token (limited to customer_a)
  3. Customer uploads file → S3 bucket/customer_a/file.txt
  4. S3 IAM policy: allow access to bucket/customer_a/* only
  5. Result: customer_a can't access bucket/customer_b/*

Security:
  ├─ Token expiry: 1 hour (automatic)
  ├─ Prefix isolation: S3 enforces customer_a/* boundary
  ├─ No manual revocation needed
  └─ Scalable: supports 1M customers
```

---

## Interview Checklist

- [ ] Lambda: cold starts 200-700ms (use for async, not API)
- [ ] S3: now strongly consistent (safe for configs)
- [ ] IAM: use STS for multi-tenant, not per-user
- [ ] Policy templates: ${variable} for customer isolation
- [ ] DynamoDB: customer_id as partition key (no cross-tenant reads)

## Common Wrong Answers

- ❌ "Lambda for all APIs" — cold starts kill latency
- ❌ "Shared IAM user for all customers" — security breach
- ❌ "No prefix validation on S3" — customers could traverse
- ❌ "Ignore S3 consistency" — lucky but wrong (now consistent anyway)
