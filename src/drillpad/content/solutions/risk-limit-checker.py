# ruff: noqa
class RiskChecker:
    def __init__(self, max_position, max_order_qty, max_order_notional, band_bps):
        self.max_pos = max_position
        self.max_qty = max_order_qty
        self.max_notional = max_order_notional
        self.band = band_bps
        self.ref = {}
        self.pos = {}
        self.open = {}   # symbol -> [open_buy, open_sell]

    def set_ref(self, symbol, price):
        self.ref[symbol] = price

    def _open(self, symbol):
        return self.open.setdefault(symbol, [0, 0])

    def check(self, symbol, side, qty, price):
        if side not in ("buy", "sell") or not isinstance(qty, int) or not isinstance(price, int) or qty <= 0 or price <= 0:
            return "BAD_ORDER"
        if qty > self.max_qty:
            return "MAX_ORDER_QTY"
        if qty * price > self.max_notional:
            return "MAX_NOTIONAL"
        ref = self.ref.get(symbol)
        if ref is not None and abs(price - ref) * 10000 > self.band * ref:
            return "FAT_FINGER"
        pos = self.pos.get(symbol, 0)
        ob, os_ = self._open(symbol)
        if side == "buy":
            if pos + ob + qty > self.max_pos:
                return "MAX_POSITION"
        elif pos - os_ - qty < -self.max_pos:
            return "MAX_POSITION"
        return "OK"

    def submit(self, symbol, side, qty, price):
        r = self.check(symbol, side, qty, price)
        if r == "OK":
            self._open(symbol)[0 if side == "buy" else 1] += qty
        return r

    def fill(self, symbol, side, qty):
        o = self._open(symbol)
        i = 0 if side == "buy" else 1
        if qty <= 0 or qty > o[i]:
            raise ValueError("fill exceeds open quantity")
        o[i] -= qty
        self.pos[symbol] = self.pos.get(symbol, 0) + (qty if side == "buy" else -qty)

    def cancel(self, symbol, side, qty):
        o = self._open(symbol)
        i = 0 if side == "buy" else 1
        if qty <= 0 or qty > o[i]:
            raise ValueError("cancel exceeds open quantity")
        o[i] -= qty

    def position(self, symbol):
        return self.pos.get(symbol, 0)

    def open_qty(self, symbol, side):
        return self._open(symbol)[0 if side == "buy" else 1]
