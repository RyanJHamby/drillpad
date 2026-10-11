# Web/Frontend for Backend Engineers

## SSR vs CSR

```
SSR (Server-Side Rendering):
  1. Request: GET /home
  2. Server: render HTML with data
  3. Response: <html><body>Welcome, John</body></html>
  4. Browser: display (fast, searchable)
  
  Pros: ✓ Fast first load, SEO, no JS errors
  Cons: ✗ Every request hits server, slower updates

CSR (Client-Side Rendering):
  1. Request: GET /home
  2. Server: returns empty HTML + app.js
  3. Browser: downloads app.js (React, Vue, etc.)
  4. JavaScript: fetches /api/user, renders HTML
  5. Display: slower, but interactive
  
  Pros: ✓ Rich interactivity, fast subsequent updates
  Cons: ✗ Slow first load, SEO harder, JS required

Hybrid (Next.js, Remix):
  ├─ SSR: initial load server-rendered
  ├─ Hydration: JavaScript takes over
  ├─ Best of both: fast + interactive
  └─ Recommended for modern apps
```

## Core Web Vitals

```
Metrics Google cares about:

LCP (Largest Contentful Paint):
  ├─ Time to paint largest element (image, text)
  ├─ Target: <2.5 seconds
  ├─ Impact: image optimization, server response time

FID (First Input Delay):
  ├─ Time from click to response
  ├─ Target: <100ms
  ├─ Impact: JavaScript blocking (remove unused JS)

CLS (Cumulative Layout Shift):
  ├─ Page layout changes while user interacts
  ├─ Example: ads load, page jumps
  ├─ Target: <0.1
  ├─ Impact: reserve space for images, ads
  
Optimization:
  ├─ Compress images (WebP format)
  ├─ Lazy load (load only visible)
  ├─ Code splitting (split JS into chunks)
  └─ Cache (CDN, browser cache)
```

## CDN (Content Delivery Network)

```
Problem: user in Tokyo, server in us-east-1
  ├─ Request latency: 100ms
  ├─ User experience: slow

CDN:
  ├─ Cache static files (JS, CSS, images) globally
  ├─ User in Tokyo → fetches from Tokyo edge
  ├─ Latency: 10ms (much better!)
  
  Examples: Cloudflare, CloudFront, Fastly
  
  Cost: $0.085 per GB (varies)
  
  What to cache:
    ├─ Images: 1 year TTL (versioned in URL)
    ├─ CSS/JS: 1 day TTL (auto-versioned)
    ├─ HTML: 5 min TTL (updates frequent)
    └─ API: don't cache (data changes)
```

## Accessibility Basics

```
A11y (web accessibility):

Keyboard navigation:
  ├─ Tab key: move between buttons, links
  ├─ Screen readers: read alt text for images
  └─ Test: try navigating with keyboard only

Alt text:
  <img src="chart.png" alt="Revenue growth 2024: $5M to $8M">
    └─ Describes image for screen readers

Semantic HTML:
  <button>Click me</button>  ✓ (accessible)
  <div onclick="...">Click me</div>  ✗ (not accessible)
  
  ├─ <button>, <a>, <form> have built-in a11y
  ├─ <div> doesn't (must add role=button, aria-*)
  └─ Always use semantic when possible

Color contrast:
  ├─ Text vs background: 4.5:1 ratio (WCAG AA)
  ├─ Light gray on white: bad
  └─ Black on white: good
```

---

## Interview Checklist

- [ ] SSR vs CSR: tradeoffs (first load vs interaction)
- [ ] Core Web Vitals: LCP, FID, CLS targets
- [ ] CDN: cache static, short TTL for HTML
- [ ] Accessibility: keyboard nav, alt text, semantic HTML
- [ ] Lighthouse: audit tool for performance

## Common Wrong Answers

- ❌ "Always CSR" — slow first load, SEO bad
- ❌ "No CDN" — global latency painful
- ❌ "No alt text" — screen readers fail
- ❌ "Cache everything" — HTML cached too long = stale
