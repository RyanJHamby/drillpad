# ruff: noqa
def ohlc(ticks, bar_secs, fill_gaps=False):
    if not isinstance(bar_secs, int) or bar_secs <= 0:
        raise ValueError("bar_secs must be a positive int")
    bars = []
    cur = None
    prev_ts = None
    for ts, price, qty in ticks:
        if prev_ts is not None and ts < prev_ts:
            raise ValueError("ticks must be sorted by timestamp")
        prev_ts = ts
        start = ts - ts % bar_secs
        if cur is not None and cur[0] == start:
            if price > cur[2]:
                cur[2] = price
            if price < cur[3]:
                cur[3] = price
            cur[4] = price
            cur[5] += qty
            continue
        if cur is not None:
            bars.append(tuple(cur))
            if fill_gaps:
                s = cur[0] + bar_secs
                while s < start:
                    bars.append((s, cur[4], cur[4], cur[4], cur[4], 0))
                    s += bar_secs
        cur = [start, price, price, price, price, qty]
    if cur is not None:
        bars.append(tuple(cur))
    return bars
