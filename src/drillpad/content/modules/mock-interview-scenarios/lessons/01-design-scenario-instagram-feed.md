# Mock Interview: Design Instagram Feed

## Prompt (Read aloud to candidate)

"Design the backend for Instagram's feed. 500M DAU, each user follows ~500 people. They scroll 10 min/day. Design for <500ms P95 latency. You have 45 minutes."

---

## Time Plan

```
0-5 min:   Requirements & clarifications
5-10 min:  Capacity estimation
10-20 min: Architecture sketch (data model, API, compute)
20-35 min: Bottleneck analysis + scale (handle 500M DAU)
35-40 min: Tradeoffs & deep dive (chosen one)
40-45 min: Q&A & follow-ups
```

---

## Scoring Rubric

Aligned to FIRM_SPECIFIC_INTERVIEW_RUBRICS.md, weighted:

**Requirements (15%)**
- [ ] Asked clarifying questions (DAU, QPS, read/write ratio)
- [ ] Identified write-heavy (new posts) + read-heavy (feed scroll)
- [ ] Clear about SLAs (P95 <500ms)

**Architecture (40%)**
- [ ] Identified bottleneck: feed generation (join 500 followers × posts)
- [ ] Data model: posts table, followers table, fanout-on-write vs fanout-on-read
- [ ] Caching layer (Redis for hot feeds)
- [ ] Partitioning strategy (by user_id)
- [ ] API design clear

**Capacity Estimation (15%)**
- [ ] Showed math: 500M DAU × 10 min × scroll rate
- [ ] Calculated QPS (orders of magnitude matter)
- [ ] Storage estimation (reasonable, not precise)

**Tradeoffs (20%)**
- [ ] Fanout-on-write vs read (latency vs compute cost)
- [ ] Consistency (eventual OK for feeds)
- [ ] Cache invalidation strategy
- [ ] Justified choice with reasoning

**Communication (10%)**
- [ ] Clear diagrams/ASCII
- [ ] Explained decisions aloud
- [ ] Responded to probes without becoming defensive

---

## Architecture Outline (Not an essay — bullets only)

```
Data model:
  users: user_id, username, ...
  posts: post_id, author_id, content, created_at
  followers: follower_id, following_id
  feed_cache: user_id → [post_ids] (Redis)

API:
  GET /feed → [list of posts, cursor for pagination]
  POST /posts → create new post
  
Compute:
  Fanout-on-write: new post → write to 500 followers' caches
  Cost: high (500 writes per post)
  Benefit: feed read is instant (join results pre-computed)

Cache layer:
  Redis: user_id → [post_ids] (top 100 posts)
  TTL: 1 hour
  Hit rate: 95% (users re-read recent posts)

Bottleneck:
  Read QPS: 500M DAU × 10 min/day / 86400 = 58K QPS
  Redis handles: 100K QPS (sufficient)
  
Scaling:
  Redis cluster: 10 nodes (replication)
  Database: partitioned by user_id (100 partitions)
```

---

## 5 Follow-Up Probes

**Probe 1 (Write Path):** "A celebrity posts. 10M followers. Walk me through what happens in your system."

*Expected strong answer:*
  - Fanout-on-write: queue 10M write jobs
  - Write in parallel to Redis
  - Cost: 10M ops in 1 sec = doable (Redis can handle)
  - Timeline: post visible to followers within seconds

*Weak answer:*
  - "Um, we just write to the database"
  - (Doesn't address 10M followers at scale)

**Probe 2 (Consistency):** "I post a photo. My best friend refreshes their feed immediately. Do they see it?"

*Expected:*
  - Yes, within 1-2 seconds (fanout-on-write)
  - Or: no, takes 1 hour (if caching without fanout)
  - Depends on tradeoff chosen, justified

*Weak:*
  - "Um, maybe?"

**Probe 3 (Storage):** "How much storage do you need for 1 year of posts?"

*Expected:*
  - 500M DAU × 1 post/day × 365 = 183B posts
  - 200 bytes/post = 36 TB
  - Reasonable (within AWS budget)

**Probe 4 (Cache Invalidation):** "User deletes a post. How do you remove it from follower caches?"

*Expected:*
  - Fanout-on-delete: async job deletes from followers' caches
  - Or: shorter TTL, let expire naturally (acceptable)
  - Or: versioned cache keys (complicated)

*Weak:*
  - "We don't need to"
  - (Deleted posts still visible)

**Probe 5 (Personalization):** "Some users mute notifications. How do you handle suppressing posts from them?"

*Expected:*
  - Mute list: user_id → [muted_user_ids] (Redis)
  - Feed generation: filter out muted users
  - Cost: low (small set, fast lookup)

*Weak:*
  - "We don't support muting"

---

## Preparation Links

- [Systems Design Process](/learn?m=systems-design-process&l=01-framework)
- [Back-of-Envelope Estimation](/learn?m=systems-design-process&l=03-back-of-envelope-estimation)
- [Caching Strategies](/learn?m=caching-strategies)
- [Database Fundamentals](/learn?m=database-fundamentals&l=01-relational-databases)
