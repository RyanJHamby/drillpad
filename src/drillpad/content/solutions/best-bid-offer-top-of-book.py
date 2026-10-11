# ruff: noqa
import heapq


class BBO:
    def __init__(self):
        self.q = {"buy": {}, "sell": {}}
        self.h = {"buy": [], "sell": []}

    def _top(self, side):
        h, q = self.h[side], self.q[side]
        while h:
            p = -h[0] if side == "buy" else h[0]
            if p in q:
                return (p, q[p])
            heapq.heappop(h)
        return None

    def bbo(self):
        return (self._top("buy"), self._top("sell"))

    def update(self, side, price, qty):
        if side not in ("buy", "sell"):
            raise ValueError("bad side")
        if not isinstance(price, int) or price <= 0 or not isinstance(qty, int) or qty < 0:
            raise ValueError("bad price/qty")
        before = self.bbo()
        q = self.q[side]
        if qty == 0:
            q.pop(price, None)
        else:
            if price not in q:
                heapq.heappush(self.h[side], -price if side == "buy" else price)
            q[price] = qty
        return self.bbo() != before

    def best_bid(self):
        t = self._top("buy")
        return None if t is None else t[0]

    def best_ask(self):
        t = self._top("sell")
        return None if t is None else t[0]

    def spread(self):
        b, a = self.best_bid(), self.best_ask()
        return None if b is None or a is None else a - b
