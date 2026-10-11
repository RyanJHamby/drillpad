# System Design: Feed Ranking & Recommendation

## Firm Archetype: Facebook, TikTok, Netflix, LinkedIn

**Problem:** Generate personalized feed for 1B users. 1000s of content items per user per day.

**Why hard:** Real-time ranking, personalization at scale, cold start.

---

## Architecture

```
Content creation:
  User posts video → Kafka (new content) → Indexing service

Feed generation:
  User scrolls → API → ML Model → Database → Results

Flow:
  1. Get user context (location, interests, friends)
  2. Candidate generation (1000 best items for user)
  3. Ranking (ML model scores each)
  4. Filtering (remove duplicates, spam)
  5. Return top 20
```

---

## Candidate Generation (Fast)

```
Goal: Find 1000 best items from 10B possible items

Naive approach:
  Score all 10B items
  Return top 20
  Time: 10 seconds (too slow)

Smart approach:
  Use heuristics to pre-filter:
  1. Recency: posts from last 24 hours (reduces 10B → 100M)
  2. Friends only: posts from user's friends (reduces 100M → 10M)
  3. Categories: posts in user's interests (reduces 10M → 1M)
  4. Engagement: high-engagement posts (reduces 1M → 100K)
  5. Score all 100K items
  
  Time: 500ms (acceptable)
```

---

## Ranking Model

```
ML Model (LightGBM):
  Input:
    - User features: age, location, interests, history
    - Content features: engagement rate, freshness, creator
    - Interaction features: user_id + content_id, similarity
  
  Output:
    - Score [0, 1] (probability user will engage)
  
  Model inference:
    - 100 items * 200 features * 1M users/day
    - Inference time: 1ms per user (fast)
    - Need: 1M * 1ms = 1000 sec compute per day (1 GPU handles)
    - But: 1M concurrent users → need 1000 GPUs (expensive!)
  
  Optimization:
    - Use CPU inference (2x slower, 100x cheaper)
    - Batch inference (offline, pre-compute before user opens app)
    - Cache results (1 hour TTL)
```

---

## Key Tradeoffs

**1. Real-time vs offline ranking**
- Real-time: ML model scores items as user scrolls (freshest)
- Offline: pre-compute top 20 (stale by hours)
- Decision: hybrid
  - Cache contains pre-computed top 20 (fast, refreshed hourly)
  - User scrolls down → real-time scoring (fresh, slower)

**2. Personalization depth**
- Simple: show popular items (1ms ranking)
- Complex: deep model, user history (500ms ranking)
- Decision: simple for P99 latency, complex for P50

**3. Diversity vs relevance**
- Relevant: show only items user likes (good click rate)
- Diverse: also show new items, creators (discovery)
- Decision: relevance 80%, diversity 20%

---

## Scaling Calculation

```
1B users
500M daily active
Each user generates feed: 20 items
Candidate generation: 1000 items per user
Feed generation: 500M DAU * (1000 + ranking) = 500B operations/day

Timeline service:
  - Read user's friends' posts (social graph)
  - Friends average: 500 friends
  - Posts: 100/day per friend
  - Total items to consider: 500 * 100 = 50K items per user
  - Filter to 1000 items (using engagement)

ML ranking:
  - Batch inference: 500M users * 1000 items / 3600s = 139M items/sec
  - Inference latency: 10µs per item
  - Total GPU compute: 139M * 10µs = 1390 seconds CPU time
  - Cost: 1390 sec / 86400 sec per day = 1.6% of 1 GPU/day
  - Cheap!
```

---

## Cold Start Problem

```
New user (no history):
  Can't use engagement history
  Can't personalize
  
Solution 1: Popular items
  Show trending items globally
  
Solution 2: Category preferences
  Ask user to pick interests (onboarding)
  Show items from those categories
  
Solution 3: Collaborative filtering
  Find similar users (by interests)
  Show items they liked
  
Implementation:
  - For first 100 impressions: use popular + category
  - After 100 impressions: switch to ML model
  - Model cold-starts automatically on fresh user
```

---

## Code Example (Python)

```python
class FeedService:
    def __init__(self):
        self.kafka = KafkaConsumer('new_posts')
        self.ml_model = MLModel.load('ranker')
        self.redis = RedisClient()
        self.graph = SocialGraphDB()
        self.posts = PostDB()
    
    def generate_feed(self, user_id, limit=20):
        """Generate personalized feed."""
        # Check cache
        cached = self.redis.get(f"feed:{user_id}")
        if cached:
            return cached
        
        # Candidate generation
        candidates = self._get_candidates(user_id)  # 1000 items
        
        # Ranking
        scored = []
        for item in candidates:
            features = self._extract_features(user_id, item)
            score = self.ml_model.predict(features)
            scored.append((item, score))
        
        # Sort and filter
        scored.sort(key=lambda x: x[1], reverse=True)
        results = [item for item, score in scored[:limit]]
        
        # Cache for 1 hour
        self.redis.set(f"feed:{user_id}", results, ttl=3600)
        return results
    
    def _get_candidates(self, user_id):
        """Get 1000 candidate items."""
        # Friends' recent posts
        friends = self.graph.get_friends(user_id)  # ~500 friends
        posts = []
        for friend in friends:
            posts.extend(self.posts.get_recent(friend, days=1))
        
        # Sort by engagement
        posts.sort(key=lambda p: p['engagement_score'], reverse=True)
        return posts[:1000]
    
    def _extract_features(self, user_id, item):
        """Extract ML features."""
        return {
            'user_age': self.redis.get(f"user:{user_id}:age"),
            'user_interests': self.redis.get(f"user:{user_id}:interests"),
            'item_engagement': item['engagement_score'],
            'item_freshness': time.time() - item['created_at'],
            'creator_followers': self.graph.get_followers(item['creator_id']),
        }
```

---

## Q&A

**Recall 1:** Why pre-compute feed offline instead of real-time?

*Must-say:*
- Real-time: 500ms ranking per user (ok)
- 500M concurrent: 500ms * 500M = way too slow
- Offline: pre-compute hourly, cache, serve instantly
- Tradeoff: stale by 1 hour (acceptable for feed)

**Probe 1:** How do you handle new posts (not in cache)?

*Expected:*
- New posts added to Kafka
- Indexing service adds to search index
- Next user's feed generation includes new posts
- So: 1-5 minute latency for new posts to appear

**Numeric 1:** 1B users, 500M DAU. Feed generation takes 500ms per user. Total compute time?

*Working:*
- 500M users * 500ms = 250M seconds
- Per day: 250M seconds / 86400 = 2893 seconds = 48 minutes
- BUT: users don't all generate feeds simultaneously
- Peak hours: 100M concurrent users generating feeds
- 100M * 0.5s = 50M seconds compute time = 14 hours
- Need: 14 hours / 1 hour = 14x parallelism (14K servers at 1 feed/sec)

