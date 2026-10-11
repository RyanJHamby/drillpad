# ruff: noqa
class OMSError(Exception):
    pass


class OMS:
    def __init__(self):
        self.orders = {}
        self.open_all = {}
        self.open_sym = {}
        self.execs = set()

    def _order(self, order_id):
        o = self.orders.get(order_id)
        if o is None:
            raise OMSError("unknown order")
        return o

    def _close(self, order_id, o, state):
        o["state"] = state
        del self.open_all[order_id]
        del self.open_sym[o["symbol"]][order_id]

    def submit(self, order_id, symbol, side, qty, limit_price):
        if order_id in self.orders or side not in ("BUY", "SELL"):
            raise OMSError("bad order")
        if type(qty) is not int or qty <= 0 or type(limit_price) is not int or limit_price <= 0:
            raise OMSError("bad order")
        o = {"symbol": symbol, "side": side, "qty": qty, "limit": limit_price, "cum": 0, "notional": 0, "state": "NEW"}
        self.orders[order_id] = o
        self.open_all[order_id] = o
        self.open_sym.setdefault(symbol, {})[order_id] = o

    def fill(self, order_id, qty, price, exec_id):
        if exec_id in self.execs:
            return False
        o = self._order(order_id)
        if o["state"] not in ("NEW", "PARTIALLY_FILLED"):
            raise OMSError("order closed")
        if type(qty) is not int or qty <= 0 or qty > o["qty"] - o["cum"]:
            raise OMSError("bad fill quantity")
        if (o["side"] == "BUY" and price > o["limit"]) or (o["side"] == "SELL" and price < o["limit"]):
            raise OMSError("limit violated")
        self.execs.add(exec_id)
        o["cum"] += qty
        o["notional"] += qty * price
        if o["cum"] == o["qty"]:
            self._close(order_id, o, "FILLED")
        else:
            o["state"] = "PARTIALLY_FILLED"
        return True

    def cancel(self, order_id):
        o = self._order(order_id)
        if o["state"] not in ("NEW", "PARTIALLY_FILLED"):
            raise OMSError("order closed")
        self._close(order_id, o, "CANCELED")
        return True

    def amend(self, order_id, new_qty):
        o = self._order(order_id)
        if o["state"] not in ("NEW", "PARTIALLY_FILLED"):
            raise OMSError("order closed")
        if type(new_qty) is not int or new_qty <= 0 or new_qty < o["cum"]:
            raise OMSError("bad quantity")
        o["qty"] = new_qty
        if new_qty == o["cum"]:
            self._close(order_id, o, "FILLED")

    def get(self, order_id):
        o = self._order(order_id)
        cum = o["cum"]
        avg = (2 * o["notional"] + cum) // (2 * cum) if cum else 0
        leaves = o["qty"] - cum if o["state"] in ("NEW", "PARTIALLY_FILLED") else 0
        return {"state": o["state"], "symbol": o["symbol"], "side": o["side"], "qty": o["qty"],
                "cum_qty": cum, "leaves_qty": leaves, "avg_px": avg}

    def open_orders(self, symbol=None):
        if symbol is None:
            return list(self.open_all)
        return list(self.open_sym.get(symbol, ()))
