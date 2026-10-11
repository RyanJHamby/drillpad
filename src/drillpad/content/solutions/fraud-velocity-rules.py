# ruff: noqa
from collections import deque, Counter


class VelocityEngine:
    def __init__(self, rules):
        self.rules = list(rules)
        self.state = [dict() for _ in self.rules]
        self.last = None

    def check(self, event):
        ts = event["ts"]
        if self.last is not None and ts < self.last:
            raise ValueError("timestamps must be non-decreasing")
        self.last = ts
        amount = event.get("amount", 0)
        fired = []
        for i, r in enumerate(self.rules):
            key = event.get(r["field"])
            if key is None:
                continue
            dfield = r.get("distinct")
            dval = None
            if dfield is not None:
                dval = event.get(dfield)
                if dval is None:
                    continue
            st = self.state[i].get(key)
            if st is None:
                st = self.state[i][key] = [deque(), 0, Counter()]
            dq = st[0]
            lo = ts - r["window"]
            while dq and dq[0][0] <= lo:
                _, a, d = dq.popleft()
                st[1] -= a
                if d is not None:
                    st[2][d] -= 1
                    if st[2][d] == 0:
                        del st[2][d]
            dq.append((ts, amount, dval))
            st[1] += amount
            if dval is not None:
                st[2][dval] += 1
            mc, ma, md = r.get("max_count"), r.get("max_amount"), r.get("max_distinct")
            if (mc is not None and len(dq) > mc) or (ma is not None and st[1] > ma) \
                    or (md is not None and dfield is not None and len(st[2]) > md):
                fired.append(r["name"])
        return fired
