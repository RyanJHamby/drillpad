# ruff: noqa
import heapq


class NBBO:
    def __init__(self):
        self.cur = {"buy": {}, "sell": {}}   # side -> venue -> (price, qty)
        self.lvl = {"buy": {}, "sell": {}}   # side -> price -> {venue: qty}
        self.heap = {"buy": [], "sell": []}

    def update(self, venue, side, price, qty):
        if side not in ("buy", "sell") or not venue:
            raise ValueError("bad side or venue")
        if qty < 0 or (qty > 0 and (not isinstance(price, int) or price <= 0)):
            raise ValueError("bad price or qty")
        old = self.cur[side].pop(venue, None)
        if old is not None:
            lv = self.lvl[side][old[0]]
            del lv[venue]
            if not lv:
                del self.lvl[side][old[0]]
        if qty == 0:
            return
        self.cur[side][venue] = (price, qty)
        lv = self.lvl[side].get(price)
        if lv is None:
            lv = self.lvl[side][price] = {}
            heapq.heappush(self.heap[side], -price if side == "buy" else price)
        lv[venue] = qty

    def _top(self, side):
        h = self.heap[side]
        while h:
            p = -h[0] if side == "buy" else h[0]
            if p in self.lvl[side]:
                lv = self.lvl[side][p]
                return (p, sum(lv.values()), tuple(sorted(lv)))
            heapq.heappop(h)
        return None

    def nbbo(self):
        return (self._top("buy"), self._top("sell"))

    def status(self):
        bid, ask = self.nbbo()
        if bid is None and ask is None:
            return "empty"
        if bid is None or ask is None:
            return "one-sided"
        if bid[0] > ask[0]:
            return "crossed"
        if bid[0] == ask[0]:
            return "locked"
        return "normal"
