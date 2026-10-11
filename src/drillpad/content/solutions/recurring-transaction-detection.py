# ruff: noqa
from collections import defaultdict


def find_recurring(transactions):
    groups = defaultdict(set)                  # (company, amount) -> distinct days
    for company, amount, day in transactions:
        groups[(company, amount)].add(day)
    recurring = set()
    for (company, _), days in groups.items():
        if company in recurring or len(days) < 3:
            continue
        ds = sorted(days)
        found = False
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                if ds[j] + (ds[j] - ds[i]) in days:   # ds[i], ds[j], ds[j] + gap
                    found = True
                    break
            if found:
                break
        if found:
            recurring.add(company)
    return sorted(recurring)
