# ruff: noqa
from collections import deque


class Position:
    def __init__(self, method="fifo"):
        if method not in ("fifo", "lifo"):
            raise ValueError("method must be fifo or lifo")
        self.method = method
        self.lots = deque()   # [qty > 0, price]; all lots share one direction
        self.dir = 0          # +1 long, -1 short, 0 flat
        self.pnl = 0

    def trade(self, side, qty, price):
        if side not in ("buy", "sell") or not isinstance(qty, int) or not isinstance(price, int) or qty <= 0 or price <= 0:
            raise ValueError("bad trade")
        d = 1 if side == "buy" else -1
        if self.dir == 0 or d == self.dir:
            self.dir = d
            self.lots.append([qty, price])
            return 0
        realized = 0
        while qty and self.lots:
            lot = self.lots[0] if self.method == "fifo" else self.lots[-1]
            take = min(qty, lot[0])
            realized += (price - lot[1]) * take * self.dir
            lot[0] -= take
            qty -= take
            if lot[0] == 0:
                if self.method == "fifo":
                    self.lots.popleft()
                else:
                    self.lots.pop()
        if not self.lots:
            self.dir = 0
        if qty:
            self.dir = d
            self.lots.append([qty, price])
        self.pnl += realized
        return realized

    def position(self):
        return self.dir * sum(l[0] for l in self.lots)

    def realized(self):
        return self.pnl

    def unrealized(self, mark):
        return sum((mark - p) * q * self.dir for q, p in self.lots)

    def open_lots(self):
        return [(self.dir * q, p) for q, p in self.lots]
