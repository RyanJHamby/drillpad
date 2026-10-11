# ruff: noqa
from collections import defaultdict


def reconcile(internal, broker):
    a = defaultdict(int)
    b = defaultdict(int)
    for tid, q in internal:
        a[tid] += q
    for tid, q in broker:
        b[tid] += q
    breaks = []
    for tid in sorted(set(a) | set(b)):
        if tid not in b:
            breaks.append((tid, "missing at broker"))
        elif tid not in a:
            breaks.append((tid, "missing internally"))
        elif a[tid] != b[tid]:
            breaks.append((tid, f"qty mismatch: internal={a[tid]}, broker={b[tid]}"))
    return breaks
