# ruff: noqa
from bisect import bisect_right, insort

_ALLOWED = {"user", "currency", "min_amount", "max_amount", "start_ts", "end_ts"}


class TransactionStore:
    def __init__(self, txns=()):
        rows = sorted(txns, key=lambda t: (-t["ts"], -t["id"]))
        self.rows = rows
        self.keys = [(-t["ts"], -t["id"]) for t in rows]

    def _insert(self, t):
        key = (-t["ts"], -t["id"])
        i = bisect_right(self.keys, key)
        self.keys.insert(i, key)
        self.rows.insert(i, t)

    def add(self, txn):
        self._insert(txn)

    def query(self, limit, cursor=None, **filters):
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be an int >= 1")
        if set(filters) - _ALLOWED:
            raise ValueError("unknown filter")
        start = 0
        if cursor is not None:
            try:
                ts_s, id_s = cursor.split(":")
                start = bisect_right(self.keys, (-int(ts_s), -int(id_s)))
            except (ValueError, AttributeError):
                raise ValueError("bad cursor")
        preds = []
        f = filters
        if f.get("user") is not None:
            preds.append(lambda t, v=f["user"]: t["user"] == v)
        if f.get("currency") is not None:
            preds.append(lambda t, v=f["currency"]: t["currency"] == v)
        if f.get("min_amount") is not None:
            preds.append(lambda t, v=f["min_amount"]: t["amount"] >= v)
        if f.get("max_amount") is not None:
            preds.append(lambda t, v=f["max_amount"]: t["amount"] <= v)
        if f.get("start_ts") is not None:
            preds.append(lambda t, v=f["start_ts"]: t["ts"] >= v)
        if f.get("end_ts") is not None:
            preds.append(lambda t, v=f["end_ts"]: t["ts"] < v)
        out = []
        rows = self.rows
        i = start
        n = len(rows)
        while i < n and len(out) <= limit:
            t = rows[i]
            if all(p(t) for p in preds):
                out.append(t)
            i += 1
        more = len(out) > limit
        page = out[:limit]
        nxt = "%d:%d" % (page[-1]["ts"], page[-1]["id"]) if more else None
        return page, nxt
