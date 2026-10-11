# System Design: Web Crawler

## Firm Archetype: Google Search, Bing, Common Crawl

**Problem:** Index the web. Crawl 1B+ pages, update frequently, respect politeness, detect duplicates, handle failures. Schedule-aware (daily crawl of news sites, weekly for blogs).

**Why hard:** Infinite web, politeness (robots.txt, politeness delay), deduplication at scale, URL frontier management, failure recovery.

---

## Architecture

```
URL Frontier (Priority Queue):
  ├─ Input: seed URLs + discovered links
  ├─ Storage: Redis priority queue per domain
  ├─ Priority: (domain_reputation, page_importance, last_crawl_time)
  └─ Output: next URL to crawl

Crawler Worker (100 workers, distributed):
  ├─ Poll: next URL from frontier
  ├─ Fetch: HTTP GET with timeout (10 sec)
  ├─ Parse: extract links, title, content
  ├─ Store: to distributed file system
  ├─ Filter: new links → add to frontier
  └─ Rate limit: 1 request/sec per domain (politeness)

Deduplication:
  ├─ Seen: set of visited URLs (Redis)
  ├─ New: filter URLs against seen set
  ├─ Collision: URL fragment (#) + query param normalization
  └─ Size: 1B URLs × 50 bytes = 50 GB (distributed)

Storage:
  ├─ Pages: HDFS (distributed file system)
  ├─ Metadata: DynamoDB (URL, title, crawl_time, checksum)
  ├─ Links: DynamoDB (from_url, to_urls[])
  └─ Frequency: crawl_schedule per domain
```

---

## URL Frontier Strategy

### FIFO (Naive)

```
Frontier: queue of URLs in crawl order
  Push: new URL
  Pop: oldest URL (FIFO)

Problem:
  - Crawls one domain exhaustively before another
  - Domain1 down → blocked waiting for timeout
  - No prioritization (sports.com same priority as bbc.com)
```

### Politeness-Aware Frontier

```
Per-domain queue:
  domain1.com: [url1, url2, url3]
  domain2.com: [url4, url5]
  domain3.com: [url6]

Scheduling:
  1. Main queue: round-robin per domain
  2. Each domain: separate rate limiter (1 req/sec)
  3. Deferral: if domain rate-limited, defer to next slot
  
  Cycle:
    Slot 1: fetch domain1.com/url1
    Slot 2: fetch domain2.com/url4
    Slot 3: fetch domain3.com/url6
    Slot 4: fetch domain1.com/url2 (domain1 rate-limit expired)

Policy (robots.txt):
  ├─ Crawl-delay: 10 seconds (wait 10s between requests)
  ├─ User-agent: *
  ├─ Disallow: /admin/, /private/
  └─ Request-rate: crawl-delay
```

### Priority Frontier

```
Score per URL:
  score = alpha * page_rank + beta * freshness + gamma * importance
  
  page_rank: incoming links (importance)
    bbc.com: 100K backlinks → score +100
    unknown_blog.com: 5 backlinks → score +0.5
  
  freshness: time since last crawl
    news_site: crawl daily (high freshness gain)
    static_blog: crawl monthly
  
  importance: estimated traffic/clicks
    bbc.com/news: high traffic
    bbc.com/archive/2010: low traffic

Heap:
  Priority queue: max-heap by score
  Pop highest priority first
```

---

## Deduplication & Normalization

### URL Normalization

```
URL: https://example.com/path?b=2&a=1#section

Canonical form:
  1. Scheme: https (always lowercase)
  2. Host: example.com (lowercase, remove www if optional)
  3. Path: /path (remove trailing /)
  4. Query: ?a=1&b=2 (sort params, remove utm_*)
  5. Fragment: #section (usually ignore, not crawled)

Example:
  https://example.com/path?b=2&a=1#top
  https://example.com/path/?a=1&b=2#section
  https://www.example.com/path?a=1&b=2
  
  All normalize to: https://example.com/path?a=1&b=2

Storage:
  canonical_url_hash: md5(canonical_url)
  Set in Redis: seen_urls = {hash1, hash2, hash3, ...}
  Size: 1B URLs × 16 bytes (MD5) = 16 GB
```

### Checksum (Content Deduplication)

```
Same content, different URLs:
  example.com/news/article-123
  example.com/news/article-123-version-2
  
  Both render to same HTML (same news content)

Detect:
  1. Fetch both pages
  2. Compute: checksum = md5(page_content)
  3. Compare: if checksums match, mark as duplicate
  4. Store: only one copy, link others

Use case:
  - Avoid indexing duplicate news articles
  - Detect mirror sites (same content)
```

---

## Failure Handling

### Crash Recovery

```
Scenario: Crawler worker crashes mid-fetch

State:
  URL in frontier: {"url": "example.com/page1", "status": "in-flight"}
  Worker: died (network failure, out of memory, bug)

Recovery:
  1. Worker heartbeat timeout: 30 seconds
  2. Orchestrator: mark URL as "in-flight" → requeue
  3. Another worker: picks up same URL
  4. Idempotency: fetch again (safe, HTTP GET is idempotent)

Deduplication:
  - URL in seen set? → don't re-crawl
  - Content checksum in store? → link existing copy
```

### Retry Strategy

```
Transient failure (network timeout):
  ├─ Retry immediately: no backoff (maybe transient)
  ├─ Max retries: 3
  ├─ On 3 failures: defer domain by 1 hour
  └─ After 1 hour: resume crawling domain

Permanent failure (404 Not Found):
  ├─ Status code: 404, 410
  ├─ Action: delete from frontier
  ├─ Update metadata: status = "deleted"
  └─ No retry

Soft error (503 Service Unavailable):
  ├─ Status code: 500, 503
  ├─ Action: defer domain by 10 minutes
  ├─ Assumption: server overloaded, will recover
  └─ Retry later
```

### Frontier Persistence

```
Problem: crash, restart, lose frontier state

Persistence:
  Frontier in Redis, snapshot to S3 hourly
  
  On crash:
    1. Restart workers
    2. Load frontier from latest S3 snapshot
    3. Resume crawling from checkpoint
    4. Loss: last 1 hour of discovered URLs
    5. Mitigation: links re-discovered on next crawl
```

---

## Scale Calculation

```
1B pages to crawl
Crawl frequency: daily (news) to monthly (static)
Average frequency: weekly

Crawl rate:
  1B pages / 7 days = 143M pages/day
  143M pages / 86400 sec = 1,655 pages/sec

Workers:
  Pages/sec per worker: 1 (1 sec politeness delay)
  Workers needed: 1,655

Capacity:
  Add 20% headroom: 2,000 workers
  Cost: 2,000 workers × $0.10/hour = $200/hour

Frontier size:
  Typical: 100M URLs in frontier (not yet crawled)
  Max: 500M URLs (spike if many new sites discovered)
  Storage: 100M URLs × 200 bytes = 20 GB (Redis)

Seen set:
  1B URLs crawled × 16 bytes (MD5) = 16 GB
  Distributed: 16 shards × 1 GB each
  Or: HyperLogLog for cardinality only (saves space)
```

---

## Politeness Policy

```
robots.txt:
  User-agent: *
  Crawl-delay: 5
  Request-rate: 1/5
  Disallow: /admin/
  Disallow: /private/
  Allow: /public/
  
Crawler behavior:
  1. Fetch /robots.txt
  2. Parse crawl-delay: 5 seconds
  3. Before fetching any page:
     ├─ Check disallow rules
     ├─ Wait crawl-delay (5 seconds)
     └─ Fetch next page
  
  4. If disallowed:
     ├─ Skip URL
     ├─ Remove from frontier
     └─ Log as blocked

User-Agent targeting:
  robots.txt can have multiple User-Agent blocks
  
  User-agent: Googlebot
  Crawl-delay: 1
  
  User-agent: *
  Crawl-delay: 10
  
  Crawler identifies: "Mozilla/5.0 Googlebot/..."
  → Matches Googlebot block: wait 1 sec
  → Other crawlers: wait 10 sec

Timeout:
  Max fetch time: 10 seconds
  If >10 sec: abort, move to next URL
  Domain penalty: count consecutive timeouts
  After 5 timeouts: defer domain 1 hour
```

---

## Code Example (Python)

```python
import requests
import hashlib
import time
from urllib.parse import urlparse, parse_qs, urlencode
from collections import defaultdict
import redis

class WebCrawler:
    def __init__(self, frontier_size=1000):
        self.frontier = {}  # domain -> deque of URLs
        self.seen = set()  # visited URLs
        self.redis = redis.Redis()
        self.rate_limiter = defaultdict(lambda: 0)  # domain -> last_fetch_time
        self.worker_id = 1
    
    def normalize_url(self, url):
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        
        # Remove fragment, sort query params, lowercase
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower()
        path = parsed.path or '/'
        
        # Remove trailing slash
        if path != '/':
            path = path.rstrip('/')
        
        # Sort query params, remove utm_*
        params = parse_qs(parsed.query, keep_blank_values=True)
        params = {k: v for k, v in params.items() if not k.startswith('utm_')}
        query = urlencode(sorted(params.items()), doseq=True) if params else ''
        
        normalized = f"{scheme}://{host}{path}"
        if query:
            normalized += f"?{query}"
        
        return normalized
    
    def add_to_frontier(self, urls, priority=1):
        """Add URLs to frontier."""
        for url in urls:
            normalized = self.normalize_url(url)
            url_hash = hashlib.md5(normalized.encode()).hexdigest()
            
            # Dedup: skip if seen
            if url_hash in self.seen:
                continue
            
            self.seen.add(url_hash)
            
            # Add to domain queue
            domain = urlparse(normalized).hostname
            if domain not in self.frontier:
                self.frontier[domain] = []
            
            self.frontier[domain].append((normalized, priority))
    
    def fetch_robots(self, domain):
        """Fetch robots.txt for domain."""
        url = f"http://{domain}/robots.txt"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.text
        except:
            pass
        return ""
    
    def parse_robots(self, robots_text, user_agent="*"):
        """Parse robots.txt."""
        lines = robots_text.split('\n')
        crawl_delay = 1
        disallow = set()
        
        for line in lines:
            line = line.split('#')[0].strip()
            if not line:
                continue
            
            key, value = line.split(':', 1) if ':' in line else (line, '')
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'user-agent' and value.lower() == user_agent.lower():
                crawl_delay = 1
            elif key == 'crawl-delay':
                crawl_delay = int(value)
            elif key == 'disallow':
                disallow.add(value)
        
        return crawl_delay, disallow
    
    def should_crawl(self, url, domain, crawl_delay, disallow):
        """Check if URL should be crawled."""
        # Rate limit: respect crawl-delay
        now = time.time()
        if domain in self.rate_limiter:
            last_time = self.rate_limiter[domain]
            if now - last_time < crawl_delay:
                return False
        
        # Check disallow
        path = urlparse(url).path
        for pattern in disallow:
            if path.startswith(pattern):
                return False
        
        return True
    
    def crawl(self):
        """Main crawl loop."""
        while self.frontier:
            # Pick domain with highest priority
            domain = max(self.frontier.keys())
            urls = self.frontier[domain]
            
            if not urls:
                del self.frontier[domain]
                continue
            
            url, priority = urls.pop(0)
            
            # Fetch robots.txt (cached)
            robots = self.redis.get(f"robots:{domain}")
            if robots is None:
                robots = self.fetch_robots(domain)
                self.redis.setex(f"robots:{domain}", 86400, robots)  # 1 day cache
            
            crawl_delay, disallow = self.parse_robots(robots.decode())
            
            # Check politeness
            if not self.should_crawl(url, domain, crawl_delay, disallow):
                # Requeue for later
                self.frontier[domain].append((url, priority))
                time.sleep(crawl_delay)
                continue
            
            # Fetch page
            try:
                resp = requests.get(url, timeout=10)
                checksum = hashlib.md5(resp.content).hexdigest()
                
                # Store metadata
                self.redis.set(f"page:{url}", {
                    'status': resp.status_code,
                    'checksum': checksum,
                    'size': len(resp.content),
                    'timestamp': time.time()
                })
                
                # Extract links
                links = self._extract_links(resp.text, url)
                self.add_to_frontier(links, priority + 1)
                
                # Update rate limiter
                self.rate_limiter[domain] = time.time()
                
            except requests.Timeout:
                # Retry with exponential backoff
                priority = max(0, priority - 1)
                self.frontier[domain].append((url, priority))
            except Exception as e:
                print(f"Error crawling {url}: {e}")
    
    def _extract_links(self, html, base_url):
        """Extract links from HTML."""
        # Simplified: real version uses BeautifulSoup or lxml
        import re
        href_pattern = r'href=(["\']?)([^\s"\'<>]+)\1'
        links = re.findall(href_pattern, html)
        return [link[1] for link in links if link[1].startswith('http')]
```

---

## Interview Checklist

- [ ] Explain URL frontier (per-domain queue, round-robin, priority)
- [ ] Politeness: robots.txt parsing, crawl-delay, rate limiting
- [ ] Deduplication: URL normalization (MD5 hash), content checksum
- [ ] Scale: 2,000 workers for 1B pages
- [ ] Failure modes: crash recovery, retry strategy, frontier persistence
- [ ] Frontier scheduling: FIFO vs priority (PageRank, freshness)
- [ ] Content deduplication: detect mirrors, duplicates

## Common Wrong Answers

- ❌ "Crawl all URLs immediately" — violates politeness, domains blacklist you
- ❌ "Single queue for all URLs" — one slow domain blocks everything
- ❌ "No deduplication" — index same page 100x from different URLs
- ❌ "Fetch robots.txt every time" — wasteful, cache for 1 day
- ❌ "Ignore robots.txt" — legal/ethical issue, domains block crawler
- ❌ "No retry on failure" — miss legitimate pages due to transient errors
