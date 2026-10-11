# ruff: noqa
class FeedHandler:
    def __init__(self):
        self.next_seq = 1
        self.pending = {}          # seq -> msg, buffered out-of-order
        self.orders = {}           # ref -> [side, price, qty]
        self.levels = {"B": {}, "S": {}}   # side -> price -> total qty
        self.anomalies = 0

    def on_message(self, seq, msg):
        if seq < self.next_seq or seq in self.pending:
            return 0
        self.pending[seq] = msg
        applied = 0
        while self.next_seq in self.pending:
            self._apply(self.pending.pop(self.next_seq))
            self.next_seq += 1
            applied += 1
        return applied

    def _reduce(self, ref, qty):
        side, price, rem = self.orders[ref]
        lv = self.levels[side]
        lv[price] -= qty
        if lv[price] == 0:
            del lv[price]
        if qty == rem:
            del self.orders[ref]
        else:
            self.orders[ref][2] -= qty

    def _apply(self, msg):
        kind = msg[0]
        if kind == "A":
            _, ref, side, price, qty = msg
            if ref in self.orders:
                self.anomalies += 1
                return
            self.orders[ref] = [side, price, qty]
            lv = self.levels[side]
            lv[price] = lv.get(price, 0) + qty
        elif kind == "D":
            ref = msg[1]
            if ref not in self.orders:
                self.anomalies += 1
                return
            self._reduce(ref, self.orders[ref][2])
        elif kind == "E":
            _, ref, qty = msg
            if ref not in self.orders or qty <= 0 or qty > self.orders[ref][2]:
                self.anomalies += 1
                return
            self._reduce(ref, qty)
        else:
            self.anomalies += 1

    def missing(self):
        out, expect = [], self.next_seq
        for s in sorted(self.pending):
            if s > expect:
                out.append((expect, s - 1))
            expect = s + 1
        return out

    def best_bid(self):
        return max(self.levels["B"]) if self.levels["B"] else None

    def best_ask(self):
        return min(self.levels["S"]) if self.levels["S"] else None

    def depth(self, side):
        lv = self.levels[side]
        return [(p, lv[p]) for p in sorted(lv, reverse=(side == "B"))]
