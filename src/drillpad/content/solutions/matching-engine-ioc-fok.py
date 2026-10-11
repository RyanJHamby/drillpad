# ruff: noqa
import heapq
from collections import OrderedDict


class Engine:
    def __init__(self):
        self.lv = {"buy": {}, "sell": {}}    # price -> OrderedDict(id -> remaining)
        self.tot = {"buy": {}, "sell": {}}   # price -> total remaining
        self.heap = {"buy": [], "sell": []}
        self.inheap = {"buy": set(), "sell": set()}
        self.where = {}

    def _key(self, side, p):
        return -p if side == "buy" else p

    def _best(self, side):
        h = self.heap[side]
        while h:
            p = -h[0] if side == "buy" else h[0]
            if p in self.lv[side]:
                return p
            heapq.heappop(h)
            self.inheap[side].discard(p)
        return None

    @staticmethod
    def _crosses(side, price, p):
        return p <= price if side == "buy" else p >= price

    def _available(self, side, price, qty):
        opp = "sell" if side == "buy" else "buy"
        got, popped = 0, []
        while got < qty:
            p = self._best(opp)
            if p is None or not self._crosses(side, price, p):
                break
            heapq.heappop(self.heap[opp])
            popped.append(p)
            got += self.tot[opp][p]
        for p in popped:
            heapq.heappush(self.heap[opp], self._key(opp, p))
        return got

    def _match(self, side, price, qty):
        opp = "sell" if side == "buy" else "buy"
        fills = []
        while qty > 0:
            p = self._best(opp)
            if p is None or not self._crosses(side, price, p):
                break
            level = self.lv[opp][p]
            while level and qty > 0:
                oid, rem = next(iter(level.items()))
                take = min(qty, rem)
                fills.append((oid, p, take))
                qty -= take
                self.tot[opp][p] -= take
                if take == rem:
                    del level[oid]
                    del self.where[oid]
                else:
                    level[oid] = rem - take
            if not level:
                del self.lv[opp][p]
                del self.tot[opp][p]
        return qty, fills

    def _rest(self, oid, side, price, qty):
        lvl = self.lv[side].get(price)
        if lvl is None:
            lvl = self.lv[side][price] = OrderedDict()
            self.tot[side][price] = 0
            if price not in self.inheap[side]:
                self.inheap[side].add(price)
                heapq.heappush(self.heap[side], self._key(side, price))
        lvl[oid] = qty
        self.tot[side][price] += qty
        self.where[oid] = (side, price)

    def submit(self, order_id, side, otype, price, qty):
        if side not in ("buy", "sell") or otype not in ("limit", "ioc", "fok", "post_only"):
            raise ValueError("bad side or type")
        if not isinstance(price, int) or not isinstance(qty, int) or price <= 0 or qty <= 0:
            raise ValueError("bad price or qty")
        if order_id in self.where:
            return ("rejected", [])
        opp = "sell" if side == "buy" else "buy"
        if otype == "post_only":
            b = self._best(opp)
            if b is not None and self._crosses(side, price, b):
                return ("rejected", [])
            self._rest(order_id, side, price, qty)
            return ("rested", [])
        if otype == "fok" and self._available(side, price, qty) < qty:
            return ("cancelled", [])
        rem, fills = self._match(side, price, qty)
        done = qty - rem
        if otype == "limit":
            if rem:
                self._rest(order_id, side, price, rem)
            return ("filled" if rem == 0 else "partial" if done else "rested", fills)
        if rem == 0:
            return ("filled", fills)
        return ("partial" if done else "cancelled", fills)

    def cancel(self, order_id):
        info = self.where.pop(order_id, None)
        if info is None:
            return False
        side, price = info
        lvl = self.lv[side][price]
        self.tot[side][price] -= lvl.pop(order_id)
        if not lvl:
            del self.lv[side][price]
            del self.tot[side][price]
        return True

    def depth(self, side):
        return [(p, self.tot[side][p]) for p in sorted(self.lv[side], reverse=(side == "buy"))]
