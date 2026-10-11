# ruff: noqa
def _r(price, remaining, length):
    return (2 * price * remaining + length) // (2 * length)


def prorate(period_start, period_end, plan_price, changes):
    if period_end <= period_start or plan_price < 0:
        raise ValueError("bad period or price")
    prev = period_start
    for ts, price in changes:
        if price < 0 or ts < period_start or ts > period_end or ts < prev:
            raise ValueError("bad change")
        prev = ts
    length = period_end - period_start
    cur = plan_price
    lines = []
    net = 0
    for ts, price in changes:
        rem = period_end - ts
        credit = _r(cur, rem, length)
        charge = _r(price, rem, length)
        lines.append({"ts": ts, "credit": credit, "charge": charge, "amount": charge - credit})
        net += charge - credit
        cur = price
    return {"lines": lines, "net": net}
