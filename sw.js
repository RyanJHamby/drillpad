const V = "drillpad-1793373718";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.method !== "GET" || new URL(r.url).origin !== location.origin) return;
  e.respondWith(caches.open(V).then(async (c) => {
    try { const res = await fetch(r); if (res.ok) c.put(r, res.clone()); return res; }
    catch (err) { const hit = await c.match(r, { ignoreSearch: true }); if (hit) return hit; throw err; }
  }));
});
