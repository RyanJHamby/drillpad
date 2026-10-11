# ruff: noqa
class Portfolio:
    def __init__(self, cash):
        self.cash = cash
        self.positions = {}


def run_backtest(ticks, strategy, cash, fee_per_share=0):
    if fee_per_share < 0:
        raise ValueError("fee must be non-negative")
    pf = Portfolio(cash)
    last_px = {}
    pending = {}       # symbol -> list of (side, qty) created on an earlier tick
    fills, rejected, curve = [], [], []
    prev = None
    for ts, sym, px in ticks:
        if prev is not None and ts < prev:
            raise ValueError("ticks must be sorted by timestamp")
        prev = ts
        for side, qty in pending.pop(sym, []):
            if side == "buy":
                cost = qty * px + qty * fee_per_share
                if cost > pf.cash:
                    rejected.append((ts, sym, side, qty))
                    continue
                pf.cash -= cost
                pf.positions[sym] = pf.positions.get(sym, 0) + qty
            else:
                pf.cash += qty * px - qty * fee_per_share
                pf.positions[sym] = pf.positions.get(sym, 0) - qty
            fills.append((ts, sym, side, qty, px))
        last_px[sym] = px
        orders = strategy.on_tick(ts, sym, px, pf) or []
        for o_sym, side, qty in orders:
            if side not in ("buy", "sell") or not isinstance(qty, int) or qty <= 0:
                raise ValueError("bad order")
            pending.setdefault(o_sym, []).append((side, qty))
        equity = pf.cash + sum(q * last_px[s] for s, q in pf.positions.items())
        curve.append((ts, equity))
    return {"cash": pf.cash, "positions": {s: q for s, q in pf.positions.items() if q != 0},
            "fills": fills, "rejected": rejected, "equity_curve": curve}
