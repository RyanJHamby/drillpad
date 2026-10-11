# ruff: noqa
from collections import deque


class WebhookDispatcher:
    def __init__(self, send, max_attempts=5, base_delay=1, max_delay=60):
        self.send = send
        self.max_attempts = max_attempts
        self.base = base_delay
        self.cap = max_delay
        self.q = {}          # url -> deque of [event_id, seq, payload, attempts, next_at]
        self.seen = {}       # url -> set of event ids
        self.seq = {}
        self.dead = []

    def enqueue(self, url, event_id, payload, now):
        if url not in self.q:
            self.q[url] = deque()
            self.seen[url] = set()
            self.seq[url] = 0
        if event_id in self.seen[url]:
            return False
        self.seen[url].add(event_id)
        self.seq[url] += 1
        self.q[url].append([event_id, self.seq[url], payload, 0, now])
        return True

    def tick(self, now):
        out = []
        for url, dq in self.q.items():
            while dq and dq[0][4] <= now:
                ev = dq[0]
                try:
                    ok = bool(self.send(url, ev[0], ev[1], ev[2]))
                except Exception:
                    ok = False
                if ok:
                    dq.popleft()
                    out.append((url, ev[0], "delivered"))
                    continue
                ev[3] += 1
                if ev[3] >= self.max_attempts:
                    dq.popleft()
                    self.dead.append((url, ev[0]))
                    out.append((url, ev[0], "dead"))
                    continue
                ev[4] = now + min(self.cap, self.base * 2 ** (ev[3] - 1))
                out.append((url, ev[0], "retry"))
                break
        return out

    def dead_letters(self):
        return list(self.dead)

    def pending(self, url):
        return len(self.q[url]) if url in self.q else 0

    def next_due(self):
        times = [dq[0][4] for dq in self.q.values() if dq]
        return min(times) if times else None
