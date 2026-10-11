# ruff: noqa
import heapq
from collections import OrderedDict


class OrderBook:
    def __init__(self):
        self.lv = {"buy": {}, "sell": {}}    # side -> price -> OrderedDict(id -> qty)
        self.tot = {"buy": {}, "sell": {}}   # side -> price -> total qty
        self.heap = {"buy": [], "sell": []}  # lazy heaps: -price for buy, price for sell
        self.where = {}                      # id -> (side, price)

    @staticmethod
    def _check(side, price, qty):
        if side not in ("buy", "sell"):
            raise ValueError("bad side")
        if not isinstance(price, int) or not isinstance(qty, int) or price <= 0 or qty <= 0:
            raise ValueError("price and qty must be positive ints")

    def _put(self, oid, side, price, qty):
        lvl = self.lv[side].get(price)
        if lvl is None:
            lvl = self.lv[side][price] = OrderedDict()
            self.tot[side][price] = 0
            heapq.heappush(self.heap[side], -price if side == "buy" else price)
        lvl[oid] = qty
        self.tot[side][price] += qty
        self.where[oid] = (side, price)

    def _drop(self, oid):
        side, price = self.where.pop(oid)
        lvl = self.lv[side][price]
        qty = lvl.pop(oid)
        self.tot[side][price] -= qty
        if not lvl:
            del self.lv[side][price]
            del self.tot[side][price]
        return side, price, qty

    def add(self, order_id, side, price, qty):
        self._check(side, price, qty)
        if order_id in self.where:
            return False
        self._put(order_id, side, price, qty)
        return True

    def cancel(self, order_id):
        if order_id not in self.where:
            return False
        self._drop(order_id)
        return True

    def modify(self, order_id, new_price, new_qty):
        if order_id not in self.where:
            if not isinstance(new_price, int) or not isinstance(new_qty, int) or new_price <= 0 or new_qty <= 0:
                raise ValueError("price and qty must be positive ints")
            return False
        side, price = self.where[order_id]
        self._check(side, new_price, new_qty)
        old = self.lv[side][price][order_id]
        if new_price == price and new_qty <= old:
            self.lv[side][price][order_id] = new_qty
            self.tot[side][price] -= old - new_qty
            return True
        self._drop(order_id)
        self._put(order_id, side, new_price, new_qty)
        return True

    def _best_price(self, side):
        h = self.heap[side]
        while h:
            p = -h[0] if side == "buy" else h[0]
            if p in self.lv[side]:
                return p
            heapq.heappop(h)
        return None

    def best(self, side):
        p = self._best_price(side)
        return None if p is None else (p, self.tot[side][p])

    def queue(self, side, price):
        lvl = self.lv[side].get(price)
        return list(lvl) if lvl else []

    def depth(self, side, n):
        prices = self.lv[side]
        if side == "buy":
            top = heapq.nlargest(n, prices)
        else:
            top = heapq.nsmallest(n, prices)
        return [(p, self.tot[side][p]) for p in top]
