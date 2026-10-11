# ruff: noqa
import heapq
import itertools
from collections import deque


class OrderBook:
    def __init__(self):
        self.levels = {"buy": {}, "sell": {}}   # side -> price -> deque([id, qty])
        self.heaps = {"buy": [], "sell": []}     # buy: -price, sell: price (lazy cleanup)
        self.orders = {}                         # id -> (side, price)
        self.ids = itertools.count(1)

    @staticmethod
    def _check(side, qty, price=1):
        if side not in ("buy", "sell"):
            raise ValueError("bad side")
        if not isinstance(qty, int) or qty <= 0 or not isinstance(price, int) or price <= 0:
            raise ValueError("price and qty must be positive ints")

    def _best(self, side):
        heap, book = self.heaps[side], self.levels[side]
        while heap:
            p = -heap[0] if side == "buy" else heap[0]
            if book.get(p):
                return p
            heapq.heappop(heap)
            book.pop(p, None)
        return None

    def _match(self, side, qty, limit):
        opp = "sell" if side == "buy" else "buy"
        book = self.levels[opp]
        fills = []
        while qty > 0:
            p = self._best(opp)
            if p is None:
                break
            if limit is not None and ((side == "buy" and p > limit) or (side == "sell" and p < limit)):
                break
            q = book[p]
            while q and qty > 0:
                oid, oqty = q[0]
                take = min(qty, oqty)
                fills.append((oid, p, take))
                qty -= take
                if take == oqty:
                    q.popleft()
                    del self.orders[oid]
                else:
                    q[0][1] -= take
        return qty, fills

    def limit(self, side, price, qty):
        self._check(side, qty, price)
        oid = next(self.ids)
        rem, fills = self._match(side, qty, price)
        if rem > 0:
            book = self.levels[side]
            if not book.get(price):
                book[price] = deque()
                heapq.heappush(self.heaps[side], -price if side == "buy" else price)
            book[price].append([oid, rem])
            self.orders[oid] = (side, price)
        return oid, fills

    def market(self, side, qty):
        self._check(side, qty)
        return self._match(side, qty, None)[1]

    def cancel(self, order_id):
        info = self.orders.pop(order_id, None)
        if info is None:
            return False
        side, price = info
        q = self.levels[side][price]
        for i, (oid, _) in enumerate(q):
            if oid == order_id:
                del q[i]
                break
        return True

    def best_bid(self):
        return self._best("buy")

    def best_ask(self):
        return self._best("sell")

    def depth(self, side):
        book = self.levels[side]
        prices = sorted((p for p, q in book.items() if q), reverse=(side == "buy"))
        return [(p, sum(x[1] for x in book[p])) for p in prices]
