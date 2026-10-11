# System Design: Real-Time Notification System

## Firm Archetype: Uber, Facebook, Slack, Discord

**Problem:** Send notifications to 100M users. Push (mobile), email (batch), in-app (websocket). Sub-second for critical alerts.

**Why hard:** Multi-channel delivery, retry logic, user preferences, scale.

---

## Architecture

```
Client sends notification:
  POST /notify
    ├─ user_id: "user:123"
    ├─ message: "Your order arrived"
    ├─ priority: "high"
    └─ channels: ["push", "email"]

API Gateway
  ├─ Validate user exists
  ├─ Check idempotency key (no duplicate sends)
  └─ Enqueue to SQS

SQS FIFO (per user)
  ├─ Guarantees order (important: don't email before push)
  └─ Dedup by idempotency key

Notification Worker (50 workers)
  ├─ Pop from SQS
  ├─ Load user preferences (Redis cache)
  ├─ For each channel:
  │  ├─ Push: send to Firebase
  │  ├─ Email: send to email service (batch)
  │  └─ In-app: send via websocket
  └─ Store delivery status (DynamoDB)

Delivery Status
  ├─ Push: delivered, failed, ignored (device offline)
  ├─ Email: queued, sent, bounced
  └─ In-app: delivered (websocket ack)
```

---

## Key Design Decisions

**1. Why SQS FIFO (not regular SQS)?**
- FIFO: preserves order (notification 1, then 2, then 3)
- Regular SQS: might deliver 2, 1, 3 (confusing)
- Tradeoff: FIFO is slower (300 QPS vs 3000 QPS)
- Decision: FIFO for correctness (order matters for user experience)

**2. Why async workers (not sync)?**
- Sync: API waits for all channels (slow, P99 = 5s if email is slow)
- Async: API returns 202 immediately (fast, P99 = 100ms)
- Tradeoff: delivery delayed (could be eventual)
- Decision: async (user sees response immediately, delivery happens in background)

**3. Why cache user preferences?**
- Without: query database per notification (slow, bottleneck)
- With: cache for 1 hour (99% hit, DB spared)
- Tradeoff: stale preferences (if user changes in < 1 hour)
- Decision: cache (acceptable for notification preferences)

**4. Why batch emails (not instant)?**
- Instant: email service hit 100M times/day (expensive, slow)
- Batch: collect emails every 5 minutes, send in bulk (cheaper)
- Tradeoff: 5-minute delay (acceptable for email)
- Decision: batch (saves cost, better for email provider)

---

## Scale Calculation

```
100M DAU
Active: 10%
Notifications/user/day: 5
QPS: 100M * 10% * 5 / 86400 = ~580 QPS
Peak: 5x = 2900 QPS

By channel:
  Push: 50% = 1450 QPS
  Email: 30% = 870 QPS
  In-app: 20% = 580 QPS

Firebase can handle: 10K QPS per account (we're at 1.5K, ok)
Email service can handle: 1M/hour batches (we're at 75M/day = ok)
```

---

## Failure Modes & Solutions

```
Firebase down:
  → Circuit breaker: skip push for 30s
  → Queue for retry (async)
  
Email service slow:
  → Batch anyway (don't wait)
  → Dead letter queue for failures
  
User offline (no websocket):
  → Message stored in DB
  → User reconnects, fetch pending messages
  
Idempotency key collision:
  → Check DynamoDB: already sent?
  → If yes, return cached status
  → If no, process (but rare, < 1/million)
```

---

## Code Example (Python)

```python
class NotificationService:
    def __init__(self):
        self.sqs = boto3.client('sqs')
        self.firebase = FirebaseClient()
        self.email = EmailService()
        self.redis = RedisClient()
        self.dynamodb = DynamoDBClient()
        self.circuit_breaker = CircuitBreaker(threshold=5, timeout=30)
    
    def send_notification(self, user_id, message, channels, idempotency_key):
        """Async send notification."""
        # Check idempotency
        cached = self.dynamodb.get_idempotent(idempotency_key)
        if cached:
            return {"status": cached["status"]}
        
        # Mark as pending
        self.dynamodb.mark_pending(idempotency_key, user_id, message)
        
        # Enqueue
        self.sqs.send_message(
            QueueUrl='notifications.fifo',
            MessageBody=json.dumps({
                'user_id': user_id,
                'message': message,
                'channels': channels
            }),
            MessageDeduplicationId=idempotency_key,
            MessageGroupId=user_id  # FIFO per user
        )
        return {"status": "pending"}
    
    def process_notification(self, user_id, message, channels):
        """Worker: send via all channels."""
        # Load preferences
        prefs = self.redis.get(f"prefs:{user_id}")
        if not prefs:
            prefs = self.dynamodb.get_preferences(user_id)
            self.redis.set(f"prefs:{user_id}", prefs, ttl=3600)
        
        # Send to each channel
        results = {}
        for channel in channels:
            if not prefs.get(f"{channel}_enabled"):
                continue
            
            if channel == "push":
                results["push"] = self._send_push(user_id, message)
            elif channel == "email":
                results["email"] = self._queue_email(user_id, message)
            elif channel == "in_app":
                results["in_app"] = self._send_websocket(user_id, message)
        
        return results
    
    def _send_push(self, user_id, message):
        """Send push via Firebase."""
        if not self.circuit_breaker.allow():
            return {"status": "skipped", "reason": "circuit open"}
        
        try:
            device_tokens = self.dynamodb.get_device_tokens(user_id)
            for token in device_tokens:
                self.firebase.send(token, message)
            return {"status": "sent"}
        except Exception as e:
            self.circuit_breaker.record_failure()
            return {"status": "failed", "error": str(e)}
```

---

## Scaling at 1B DAU

```
Changes:
  - Partition users by shard (1-100) for parallelism
  - Each shard: independent queue + workers
  - Use Redis cluster (100 nodes) for preferences
  - Email batching: 50 batch jobs in parallel
  - Add monitoring (latency, delivery rate, failures)
```

---

## Q&A

**Recall 1:** Why FIFO queue instead of regular queue?

*Must-say:*
- FIFO: preserves order (notification 1, then 2)
- Regular: could deliver out of order (confusing)
- Tradeoff: FIFO slower (300 QPS vs 3000)
- Worth it: for correctness

**Probe 1:** What if Firebase is slow? How do you handle?

*Expected:*
- Circuit breaker: fail fast after N failures
- Queue for retry: async reprocessing
- Fallback: skip push, use in-app + email

**Numeric 1:** 100M DAU, 5 notifications/day. Peak is 5x. QPS?

*Working:*
- 100M * 5 / 86400 = 5787 QPS average
- Peak: 5787 * 5 = 28,935 QPS
- (Or simpler: 100M / 86400 * 5 * 5x = ~29K QPS)

