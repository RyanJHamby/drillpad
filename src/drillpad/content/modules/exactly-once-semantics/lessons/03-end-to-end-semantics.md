# End-to-End Exactly-Once: Watermarks, Offsets, Checkpointing

## Problem: Exactly-Once Across Multiple Stages

Single-service exactly-once (via idempotency key) is solved. But what about:

```
Source (API) → Stream (Kafka) → Processing → Sink (DB)

Exactly-once requires:
  1. Source: don't duplicate messages
  2. Stream: preserve ordering
  3. Processing: idempotent operations
  4. Sink: atomic writes
  5. On failure: resume from checkpoint
```

---

## Watermarks & Checkpoints

**Watermark:** Timestamp of "all data up to this point has been processed"

```
Stream events: 
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  
Watermark at 5:
  [1, 2, 3, 4, 5] ← processed
  [6, 7, 8, 9, 10] → not yet processed
  
On crash at event 7:
  Checkpoint stores: "watermark = 5"
  On restart: resume from event 6
```

**Checkpoint:** Durable record of (watermark, processing state)

```
Checkpoint table:
┌──────────┬──────────┬──────────────┐
│ offset   │ time     │ state        │
├──────────┼──────────┼──────────────┤
│ 100      │ 10:00:00 │ [batch data] │
│ 150      │ 10:01:00 │ [batch data] │
│ 200      │ 10:02:00 │ [batch data] │
└──────────┴──────────┴──────────────┘

On recovery: read last checkpoint (offset 200), resume from 201
```

---

## Kafka Exactly-Once Pattern

```python
from kafka import KafkaConsumer, KafkaProducer
import json

consumer = KafkaConsumer(
    'payments',
    group_id='payment-processor',
    auto_offset_reset='earliest',
    enable_auto_commit=False  # Manual offset management
)

producer = KafkaProducer()
db = Database()

for message in consumer:
    offset = message.offset
    payment = json.loads(message.value)
    
    # Idempotency check
    if db.has_processed(payment['idempotency_key']):
        continue
    
    # Process
    result = charge_payment(payment)
    
    # Atomic: write result + commit offset
    db.begin_transaction()
    db.store_result(payment['idempotency_key'], result)
    consumer.commit_async(offsets={
        message.topic_partition: message.offset + 1
    })
    db.commit_transaction()
```

**Key:** Offset commit + result write are atomic (same transaction or ordered operations).

---

## Zonevex Story: Redis Streams Exactly-Once

Your resume: "Built async LLM-OCR pipeline, 86% accuracy against 350 real ERCOT outcomes"

**Setup:** Zonevex extracts financing terms from county records (PDF → OCR → LLM → DB).

```
Architecture:
  Upload PDF → Redis Stream (FIFO)
    ↓ (offset tracking)
  LLM-OCR Worker (async)
    ↓ (process + idempotency)
  DynamoDB (store results)
    ↓ (mark processed)
  Commit Offset (Redis)
```

**Implementation (Redis Streams):**

```python
import redis
import json

r = redis.Redis()
stream_key = 'ocr_jobs'
group_name = 'ocr_group'

# Create consumer group
r.xgroup_create(stream_key, group_name, id='$', mkstream=True)

while True:
    # Read from stream
    messages = r.xreadgroup(
        groupname=group_name,
        consumername='worker-1',
        streams={stream_key: '>'},
        count=1,
        block=0
    )
    
    for stream, message_list in messages:
        message_id, data = message_list[0]
        payload = json.loads(data[b'payload'])
        
        # Idempotency: check if processed
        idempotency_key = payload['pdf_id']
        if db.has_processed(idempotency_key):
            r.xack(stream_key, group_name, message_id)
            continue
        
        # Process (LLM-OCR)
        try:
            result = ocr_and_extract(payload['pdf_url'])
            db.store_result(idempotency_key, result)
            
            # Acknowledge (offset commit)
            r.xack(stream_key, group_name, message_id)
        except Exception as e:
            # Don't acknowledge, retry later
            log_error(f"Failed: {idempotency_key}", e)
```

**Guarantees:**
- Redis Stream orders messages (FIFO)
- Consumer group tracks offset (which messages processed)
- Idempotency prevents duplicate processing
- Async LLM calls (no blocking)

---

## Q&A

**Recall 1:** What's a watermark? Why does checkpointing matter?

*Must-say:*
- Watermark: timestamp of last processed event
- Checkpoint: durably store watermark
- On crash: resume from checkpoint (no reprocessing before watermark)

**Probe 1:** Stream has events 1-100. You process 1-50, crash. Offset is 50. On restart, do you reprocess 1-50?

*Expected:*
- No, checkpoint stored offset=50
- Resume from 51
- Events 1-50 already in DB

**Numeric 1:** 1000 events/sec. Checkpoint every 10 seconds. On crash, max events reprocessed?

*Working:*
- 10 seconds * 1000 events/sec = 10,000 events
- Idempotency deduplicates these
- Safe to reprocess (exactly-once guaranteed)

---

## Questions for the Interviewer

- How often do you checkpoint? (1s, 10s, per-batch?)
- What happens if checkpoint service is down?
- Have you had duplicate processing due to checkpoint failures?
- Do you deduplicate at the stream level or application level?
