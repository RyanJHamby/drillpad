# ruff: noqa
from bisect import bisect_left, insort
from collections import defaultdict


def dedupe(transactions, window=None):
    seen_ids = set()
    kept_ts = defaultdict(list)       # (account, amount, description) -> sorted timestamps of KEPT txns
    out = []
    for txn in transactions:
        tid = txn.get("id")
        if tid is not None and tid in seen_ids:
            continue
        if window is not None:
            key = (txn["account_id"], txn["amount"], txn["description"])
            ts = txn["timestamp"]
            lst = kept_ts[key]
            i = bisect_left(lst, ts - window)
            if i < len(lst) and lst[i] <= ts + window:
                continue
            insort(lst, ts)
        if tid is not None:
            seen_ids.add(tid)
        out.append(txn)
    return out
