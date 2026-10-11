# Pagination, Filtering, Rate Limiting: Common Patterns

## The Core Problem

API endpoint: `GET /orders` 

Your database has 10 million orders. Do you return all 10M rows?

No. The response would:
- Take 30 seconds to serialize
- Use 10GB of memory
- Time out the client

Solution: **Pagination** — return one page at a time.

## Pagination Strategies

### Strategy 1: Offset-Based (Simplest, Most Broken)

```
GET /orders?limit=100&offset=0      → orders 0-99
GET /orders?limit=100&offset=100    → orders 100-199
GET /orders?limit=100&offset=100000 → orders 100000-100099
```

**How it works:** Skip first N rows, return next M.

**Pros:** Intuitive, jump to any page

**Cons (Critical):**
- **TOCTOU race:** If rows 50-100 get deleted between requests, you skip data
- **Slow on large offsets:** `OFFSET 1000000` scans 1M rows then discards them
- **Unstable during mutations:** Inserting new orders shifts page boundaries

### Strategy 2: Cursor-Based (Standard for Production)

```
GET /orders?limit=100                     → {items: [...], next_cursor: "abc123"}
GET /orders?limit=100&cursor=abc123       → {items: [...], next_cursor: "def456"}
GET /orders?limit=100&cursor=def456       → {items: [...], next_cursor: null}
```

**How it works:** Return a pointer to the next batch, not a number.

Cursor is typically: base64(id=5000, timestamp=2025-01-15)

**Pros:**
- **Stable:** Cursor moves with the data, not affected by insertions
- **Fast:** Can use indexed lookups (e.g., `WHERE id > 5000`)
- **Efficient:** No scanning rows you'll discard

**Cons:**
- Can't jump to page 50 (no way to know what cursor is for page 50)
- Slightly more complex to implement

### Strategy 3: Seek-Based (Best Hybrid)

```
GET /orders?limit=100&after_id=5000  → orders after ID 5000
```

**Like cursor-based but simpler:** Just use the last item's ID as the cursor.

**Pros:** Simple, fast, stable
**Cons:** Only works if you're sorting by ID

### When to Use Each

| Strategy | Use case |
|---|---|
| **Offset** | Small results (<10K rows), internal APIs, not user-facing |
| **Cursor** | Large datasets, user-facing (1M+ rows), stable ordering required |
| **Seek** | Sorting by primary key only, simplicity matters |

## Filtering: Narrowing Results

### Simple Filtering

```
GET /orders?status=completed&user_id=123
  → orders where status='completed' AND user_id=123
```

### Complex Filtering (Advanced)

```
GET /orders?filter=status:completed,created_at:>2025-01-01
```

Or more sophisticated query languages:

```
GET /orders?filter=(status='completed' OR status='pending') AND amount > 100
```

### Pitfalls

| Pitfall | Impact | Fix |
|---|---|---|
| **Unindexed filters** | `WHERE status=?` scans all rows if no index | Create composite index on (user_id, status) |
| **Too many filter combinations** | API becomes unmaintainable | Limit to most common filters, document |
| **Injection vulnerabilities** | SQL injection if not sanitized | Use parameterized queries, never string concat |
| **No filter validation** | Malformed filters → 500 errors | Validate filter syntax, return 400 |

## Rate Limiting: Protecting the Service

Problem: One client hammers your API with 100K requests/second. Everyone else gets 503.

Solution: Rate limiting — deny requests once threshold is hit.

### Rate Limiting Strategies

**Strategy 1: Token Bucket (Most Common)**

```
User has 100 tokens/minute (refill at 100/60 = 1.67 tokens/sec)

Request 1: Use 1 token → 99 remaining → allowed
Request 2-100: Each uses 1 token → 0 remaining
Request 101: No tokens → DENIED (429 Too Many Requests)

Tokens refill over time.
```

**Good for:** Bursty traffic (sudden spike of 10 requests, then quiet)

**Strategy 2: Sliding Window (More Accurate)**

```
Last 60 seconds: count requests
If count >= 100: deny
Else: allow + increment counter
```

**Good for:** Strict enforcement (must stay under 100/min exactly)

**Strategy 3: Fixed Window (Simplest)**

```
Every minute: reset counter
If counter >= 100: deny
Else: increment
```

**Good for:** Simple cases, easy to understand

### Rate Limit Response

```http
HTTP 429 Too Many Requests

X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 2025-01-15T12:05:00Z
Retry-After: 45

{
  "error": "rate limit exceeded",
  "retry_after_seconds": 45
}
```

Client should read `Retry-After` and wait before retrying.

## Interview Pattern: Pagination Under Scale

```
Q: "You have a user-facing API for orders. 50M orders in the DB.
   How do you paginate efficiently?"

Weak answer:
  "Use OFFSET and LIMIT"
  (❌ Works fine for test data, breaks in production)

Strong answer:
  "I'd use cursor-based pagination:
  
  1. Why not offset?
     - OFFSET 1000000 scans 1M rows then throws them away
     - Inserting new orders shifts pages (users see duplicates)
     - Unstable for real-time data
  
  2. Cursor approach:
     - Store (id, created_at) as cursor
     - Query: SELECT * FROM orders WHERE (id, created_at) > (5000, '2025-01-01') LIMIT 100
     - Uses composite index → O(log N) lookup
     - Stable even if orders are inserted
  
  3. In response:
     {
       'items': [...],
       'next_cursor': 'eyJpZCI6IDUwOTksICJjYiI6ICI...'
     }
     (Cursor is opaque to client—just pass it back)
  
  4. Performance:
     - First page: O(log N) lookup + scan 100 rows
     - All pages equally fast (no slow later pages)
     - 50M orders, still <10ms per page
  
  Alternative if sorting by ID only:
    Seek-based (just use last_id as cursor) is simpler, same speed."

Why this signals good judgment:
  - You understood the OFFSET pitfall (not just 'add LIMIT')
  - You chose the right pagination for scale (not premature)
  - You thought about stability (TOCTOU awareness)
  - You could estimate performance (O(log N) with index)
```

## What This Signals

- You've shipped APIs that handle real scale (not just toy examples)
- You understand pagination trade-offs (offset vs cursor vs seek)
- You think about stability under mutations (TOCTOU, shifting boundaries)
- You use rate limiting to protect infrastructure (not optional)
