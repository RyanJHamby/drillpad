# SQS FIFO & DynamoDB: Implementing Exactly-Once with Idempotency Keys

## SQS FIFO Guarantees

SQS FIFO (First-In-First-Out) queue provides:
- **Ordering:** Messages processed in order (FIFO)
- **Deduplication:** Messages with same `MessageDeduplicationId` within 5 minute window are deduplicated
- **At-least-once delivery:** Messages delivered 1+ times

```python
import boto3

sqs = boto3.client('sqs')

# Send message with deduplication ID
sqs.send_message(
    QueueUrl='https://sqs.us-east-1.amazonaws.com/123456789/MyQueue.fifo',
    MessageBody='{"order_id": 123, "amount": 100}',
    MessageDeduplicationId='order-123-abc',  # Idempotency key
    MessageGroupId='seller-456'  # Ensures FIFO within group
)

# Consumer receives message, deduplicates automatically
# If same MessageDeduplicationId sent again within 5 min:
#   SQS doesn't deliver (deduplicated at queue level)
```

**Limitation:** Deduplication only lasts 5 minutes. For longer retention, use DynamoDB.

---

## DynamoDB Conditional Writes

DynamoDB provides atomic **conditional writes** for idempotency:

```python
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Idempotency')

def process_payment(user_id, amount, idempotency_key):
    """
    Atomic write: only process if idempotency_key not seen.
    """
    try:
        # Conditional put: only succeeds if key doesn't exist
        table.put_item(
            Item={
                'idempotency_key': idempotency_key,
                'user_id': user_id,
                'amount': amount,
                'status': 'IN_PROGRESS',
                'timestamp': int(time.time())
            },
            ConditionExpression='attribute_not_exists(idempotency_key)'
        )
        
        # We won the race, process the payment
        result = charge_payment(user_id, amount)
        
        # Update status
        table.update_item(
            Key={'idempotency_key': idempotency_key},
            UpdateExpression='SET #status = :status, result = :result',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':result': result
            }
        )
        
        return result
        
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        # Key already exists, fetch and return previous result
        response = table.get_item(Key={'idempotency_key': idempotency_key})
        return response['Item'].get('result', {'status': 'processing'})
```

**Guarantees:**
- Atomic: either insert succeeds or fails (no partial state)
- Durable: persisted to disk
- Global: across entire system (even multiple instances)

---

## SQS FIFO + DynamoDB Pattern

Combine both for production-grade exactly-once:

```
Architecture:
  Client
    ↓ (order with idempotency_key)
  API
    ↓ (validate, send to SQS)
  SQS FIFO Queue (deduplicates within 5 min)
    ↓ (message)
  Worker
    ↓ (check DynamoDB for idempotency_key)
  DynamoDB
    ↓ (if new: insert, process; if exists: return cached result)
  Charge Payment / Update Order
    ↓
  Mark Complete in DynamoDB
```

**Flow:**
1. Client sends: `POST /orders?idempotency_key=abc123`
2. API validates, sends to SQS FIFO with `MessageDeduplicationId=abc123`
3. SQS deduplicates within 5 min window
4. Worker polls SQS, gets message
5. Worker queries DynamoDB: "Have I seen idempotency_key=abc123?"
6. DynamoDB: Atomic conditional insert
   - If new: insert IN_PROGRESS, process payment
   - If exists: return cached result
7. Worker sends result back to API
8. API returns to client

---

## Real Example: Payment Adapter (AWS Marketplace)

Your implementation (Resume claim: "SQS FIFO + DynamoDB conditional writes"):

```python
class PaymentAdapter:
    def __init__(self):
        self.sqs = boto3.client('sqs')
        self.dynamodb = boto3.resource('dynamodb')
        self.idempotency_table = self.dynamodb.Table('payment_idempotency')
    
    def process_payment(self, seller_id, amount, idempotency_key):
        """
        Exactly-once payment processing via SQS FIFO + DynamoDB.
        """
        # Step 1: Atomic check-and-set in DynamoDB
        try:
            self.idempotency_table.put_item(
                Item={
                    'idempotency_key': idempotency_key,
                    'seller_id': seller_id,
                    'amount': amount,
                    'status': 'processing',
                    'created_at': int(time.time())
                },
                ConditionExpression='attribute_not_exists(idempotency_key)'
            )
            # We won, process the payment
            is_new = True
        except ConditionalCheckFailedException:
            # Already processed, fetch result
            response = self.idempotency_table.get_item(
                Key={'idempotency_key': idempotency_key}
            )
            cached = response['Item']
            if cached['status'] == 'completed':
                return cached['result']
            else:
                return {'status': 'processing'}
        
        # Step 2: Process payment (async callback)
        try:
            charge_id = self.payment_provider.charge(seller_id, amount)
            result = {'status': 'success', 'charge_id': charge_id}
        except Exception as e:
            result = {'status': 'failed', 'error': str(e)}
        
        # Step 3: Update DynamoDB with result
        self.idempotency_table.update_item(
            Key={'idempotency_key': idempotency_key},
            UpdateExpression='SET #status = :status, result = :result',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'completed',
                ':result': result
            }
        )
        
        return result
```

**Result:** Japanese seller onboarding 6 days → 5 minutes (from resume).

---

## Q&A

**Recall 1:** What does SQS FIFO deduplication do?

*Must-say:*
- Deduplicates messages with same `MessageDeduplicationId` within 5 min
- Prevents duplicate message delivery
- Combined with DynamoDB: exactly-once for longer windows

**Probe 1:** Idempotency key abc123 is processed. Response lost. Worker retries from SQS. What happens?

*Expected:*
- SQS sees duplicate MessageDeduplicationId, doesn't deliver duplicate
- If somehow delivered again:
  - DynamoDB conditional put fails (key exists)
  - Worker returns cached result

**Numeric 1:** Payments: 10,000/sec. DynamoDB write: 5ms. How much latency added by idempotency?

*Working:*
- Sequential: 5ms per write
- Throughput: 1000/10,000 = 10% overhead (5ms added per request)
- Total latency: payment process + 5ms idempotency check

---

## Questions for the Interviewer

- Do you use SQS FIFO in production? (cost vs benefit?)
- How long do you keep idempotency keys? (DynamoDB TTL?)
- What's your fallback if DynamoDB is down? (at-least-once?)
- Have you had race conditions with concurrent requests? (how detected?)
