# ruff: noqa
from collections import Counter


def least_interval(tasks, n):
    if not tasks:
        return 0
    counts = Counter(tasks)
    maxf = max(counts.values())
    ties = sum(1 for c in counts.values() if c == maxf)
    return max(len(tasks), (maxf - 1) * (n + 1) + ties)
