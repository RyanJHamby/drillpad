# System Design: Chat & Messaging

## Firm Archetype: Facebook Messenger, Slack, Discord, WhatsApp

**Problem:** Real-time chat for 500M users. Delivery guarantees, message ordering, presence (who's online), offline sync, typing indicators.

**Why hard:** Ordering at scale, delivery semantics (at-least-once, exactly-once), presence management, offline buffering, fan-out to multiple devices.

---

## Delivery Semantics

```
At-most-once: message may not arrive (Slack OK, trading bad)
  - Fire and forget
  - Fast, but unreliable

At-least-once: message always arrives, may arrive 2x (better)
  - Sender: keep message until ACK
  - Receiver: deduplicate by message ID
  - Used by: Kafka, TCP, email
  - Slack: acceptable (user retries)

Exactly-once: message arrives once (hardest)
  - Requires: idempotent writes + deduplication
  - Used by: database transactions, financial systems
  - Chat: overkill (at-least-once + dedup sufficient)
```

---

## Architecture

```
User A sends message to User B:

1. Client (A) creates message:
   {
     message_id: "uuid-123",
     sender: "user_a",
     receiver: "user_b",
     text: "hello",
     timestamp: 1609459200000,
     status: "pending"
   }

2. Client → API Gateway (HTTPS)
   POST /messages/send
     ├─ Idempotency key: message_id
     ├─ Returns 202 (accepted, async)
     └─ Client updates UI: "sending..."

3. API → Message Queue (SQS/Kafka)
   ├─ Enqueue: {message_id, sender, receiver, text, ts}
   └─ Dedup by message_id (no duplicates)

4. Worker pulls from queue:
   ├─ Store in DB: messages table (immutable write)
   ├─ Update inbox index: receiver_id → [msg_id, ...]
   └─ Emit event: message.created

5. WebSocket server (User B connected):
   ├─ Listen to: messages.created filter(receiver=user_b)
   ├─ Send to B: {message_id, sender, text, timestamp}
   ├─ B sends back: ACK {message_id, status: "delivered"}
   └─ Update DB: message.status = "delivered"

6. Client (A) polling for ACKs:
   ├─ GET /messages/{message_id}/status
   ├─ Server: returns "delivered" or "failed"
   └─ A's UI: update to "delivered"

User B offline (no WebSocket):
   ├─ Message stored in DB (step 4 completes)
   ├─ B offline message queue in Redis: user_b → [msg_ids]
   ├─ When B reconnects:
   │  ├─ Server: GET /messages?from=last_fetch_time
   │  ├─ Return: batch of messages + offline count
   │  └─ B's client marks as delivered
```

---

## Message Ordering (Critical)

```
Problem: Two messages arrive out-of-order
  A: "Are you free?"
  B: "Yes, let's meet"
  
  Network delay: A's message takes 500ms, B's takes 100ms
  Receiver sees: "Yes, let's meet" then "Are you free?" (confusing)

Solution 1: Sequence numbers (per conversation)
  Message: {seq: 1, text: "Are you free?"}
  Message: {seq: 2, text: "Yes, let's meet"}
  
  Receiver: sort by seq, apply in order
  But: works for 1-to-1 only, not group chat

Solution 2: FIFO queue per conversation
  Group chat rooms: Kafka topic per room
  1-to-1 chat: SQS FIFO per conversation pair
  
  Each message tagged with conversation_id
  Queue ordering guarantee: messages processed in order
  
  Cost: FIFO slower (300 QPS vs 3000 QPS)

Solution 3: Timestamp + total order (NTP sync)
  Assign ts at server receive time (not client)
  Sort by: (timestamp, message_id)
  All receivers see same order
  
  Dependency: clock accuracy (NTP critical)
```

---

## Presence (Who's Online?)

```
User B opens app:
  1. WebSocket connect
  2. Emit: presence.status {user_id: "user_b", status: "online"}
  3. Presence service (Redis):
     ├─ Add to set: online_users = {user_a, user_b, ...}
     ├─ Set TTL: 5 minutes (heartbeat)
     └─ On disconnect: remove from set

User A queries presence of User B:
  1. Check Redis: user_b in online_users?
  2. If yes: "online" (false positive possible if TTL expired)
  3. If no: "offline"
  
  False positive: User disconnects, Redis not updated
    → Heartbeat + TTL mitigates (max 5 min stale)

Typing indicators:
  User A typing message:
  1. POST /conversations/{conv_id}/typing
  2. Emit event: typing.started {user_id: "user_a"}
  3. User B sees: "User A is typing..."
  4. Expire after 3 sec (stop indicator)
  
  Naive: too many requests
    → Client: only send if not sent in last 3 sec
    → Server: debounce with TTL
```

---

## Database Schema

```
Messages table (immutable):
  PK: (conversation_id, message_id)
  - sender_id
  - text
  - timestamp (server time, immutable)
  - status: "sent" | "delivered" | "read"
  - created_at, updated_at
  
  Index: (conversation_id, timestamp DESC)
    → Fast "fetch last 50 messages"

Conversations table:
  PK: conversation_id
  - participants: [user_a, user_b]
  - last_message_id
  - last_message_timestamp
  - is_group: bool
  
  Index: (user_id) → GSI for "list my conversations"

Inbox (denormalized for speed):
  PK: user_id
  - conversations: [{conv_id, last_msg_id, unread_count}]
  - Updated on message arrival
  - Eventual consistency OK

Offline queue (Redis):
  user_id → [message_ids not yet delivered]
  TTL: 7 days
  
  On user reconnect:
    → Fetch messages from store
    → Clear queue
```

---

## Failure Modes

```
Network partition (user offline):
  - Message stored in DB (always)
  - Offline queue in Redis (7 days)
  - User reconnects: fetch missed messages
  - Mitigation: store 7 days, user must reconnect

Duplicate messages (idempotency key):
  - Client sends: message_id = uuid
  - Server: check if message_id already exists
  - If yes: return cached response (don't process again)
  - Dedup in queue: SQS/Kafka dedup by message_id
  
Stale presence (user disconnected but status = online):
  - TTL in Redis: 5 minutes
  - Heartbeat: client sends ping every 3 minutes
  - On disconnect: remove from online_users immediately
  - Max staleness: 3 min (if heartbeat fails)
  
Message loss (crash before persist):
  - Client: buffer locally until ACK
  - Server: write-through to DB before ACK
  - Queue: retry on worker failure
```

---

## Scale Calculation

```
500M users
Active daily: 50% = 250M
Messages/user/day: 10 (average)

QPS:
  Messages sent: 250M * 10 / 86400 = 28,935 QPS average
  Peak: 5x = 144,675 QPS
  
  Message reads (fetch): 100M/day = 1,157 QPS (low)
    → Mostly cached in client

Storage:
  250M users * 10 msgs/day * 365 days * 500 bytes = 456 TB/year
  
  Retention: 7 days in hot (recent messages)
  → 500M * 70 messages * 500 bytes = 17.5 TB hot
  
  Archive: >7 days in cold storage (S3)

Sharding:
  Partition by: conversation_id (hash)
  100 shards × 140K convs = 14M conversations/shard
  Each shard: 700K messages/shard/day
```

---

## Code Example (Python)

```python
import asyncio
import json
from datetime import datetime, timedelta
import redis
import boto3

class ChatService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.messages_table = self.dynamodb.Table('messages')
        self.conversations_table = self.dynamodb.Table('conversations')
        self.redis = redis.Redis()
        self.sqs = boto3.client('sqs')
    
    def send_message(self, sender_id, receiver_id, text, message_id):
        """Send 1-to-1 message with deduplication."""
        conv_id = self._make_conv_id(sender_id, receiver_id)
        
        # Check dedup
        existing = self.messages_table.get_item(
            Key={'conv_id': conv_id, 'message_id': message_id}
        )
        if existing:
            return {"status": "sent", "message_id": message_id}
        
        # Store message (immutable)
        timestamp = int(datetime.now().timestamp() * 1000)
        self.messages_table.put_item(
            Item={
                'conv_id': conv_id,
                'message_id': message_id,
                'sender_id': sender_id,
                'text': text,
                'timestamp': timestamp,
                'status': 'sent',
                'created_at': timestamp
            }
        )
        
        # Enqueue for delivery
        self.sqs.send_message(
            QueueUrl='messages.fifo',
            MessageBody=json.dumps({
                'message_id': message_id,
                'conv_id': conv_id,
                'receiver_id': receiver_id,
                'sender_id': sender_id,
                'text': text
            }),
            MessageDeduplicationId=message_id,
            MessageGroupId=conv_id
        )
        
        return {"status": "pending", "message_id": message_id}
    
    def fetch_messages(self, conv_id, limit=50, before_ts=None):
        """Fetch recent messages from conversation."""
        query_params = {
            'KeyConditionExpression': 'conv_id = :cid',
            'ExpressionAttributeValues': {':cid': conv_id},
            'ScanIndexForward': False,  # DESC by timestamp
            'Limit': limit
        }
        
        if before_ts:
            query_params['ExpressionAttributeValues'][':ts'] = before_ts
            query_params['KeyConditionExpression'] += ' AND #ts < :ts'
            query_params['ExpressionAttributeNames'] = {'#ts': 'timestamp'}
        
        response = self.messages_table.query(**query_params)
        messages = sorted(
            response['Items'],
            key=lambda m: m['timestamp']  # Sort ASC for display
        )
        return messages
    
    def mark_as_delivered(self, conv_id, message_id):
        """Update message status to delivered."""
        self.messages_table.update_item(
            Key={'conv_id': conv_id, 'message_id': message_id},
            UpdateExpression='SET #status = :st, updated_at = :now',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':st': 'delivered',
                ':now': int(datetime.now().timestamp() * 1000)
            }
        )
    
    def set_presence(self, user_id, status='online'):
        """Set user online/offline status."""
        if status == 'online':
            self.redis.setex(f"presence:{user_id}", 300, 'online')  # 5 min TTL
        else:
            self.redis.delete(f"presence:{user_id}")
    
    def get_presence(self, user_id):
        """Get user presence."""
        return 'online' if self.redis.exists(f"presence:{user_id}") else 'offline'
    
    def fetch_offline_messages(self, user_id):
        """Get messages while user was offline."""
        queue_key = f"offline:{user_id}"
        message_ids = self.redis.lrange(queue_key, 0, -1)
        
        messages = []
        for msg_id in message_ids:
            # Note: need conv_id; use secondary lookup
            # In production: denormalize in Redis
            pass
        
        self.redis.delete(queue_key)
        return messages
    
    @staticmethod
    def _make_conv_id(user_a, user_b):
        """Canonical conversation ID (order-independent)."""
        return ':'.join(sorted([user_a, user_b]))
```

---

## Interview Checklist

- [ ] Explain message ordering (FIFO queue vs sequence numbers vs NTP timestamps)
- [ ] Delivery semantics: at-most-once vs at-least-once vs exactly-once
- [ ] Idempotency: message_id deduplication
- [ ] Offline messages: Redis queue + 7-day retention
- [ ] Presence: Redis TTL + heartbeat
- [ ] Typing indicators: debounced, 3-sec expiry
- [ ] Conversation partitioning (hash-based sharding)
- [ ] Database schema: immutable messages, denormalized inbox

## Common Wrong Answers

- ❌ "Just store all messages in a single table" — doesn't scale to 144K QPS
- ❌ "Order by client timestamp" — clock skew, messages out-of-order
- ❌ "Presence with no TTL" — user appears online forever after crash
- ❌ "Fetch all messages every time" — O(n), no pagination
- ❌ "Delete messages immediately" — user offline, no history
- ❌ "No deduplication" — network retry causes duplicates
