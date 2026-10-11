# ruff: noqa
def max_non_overlapping(orders):
    for s, e in orders:
        if e <= s:
            raise ValueError("end must be after start")
    count = 0
    last_end = None
    for s, e in sorted(orders, key=lambda x: (x[1], x[0])):
        if last_end is None or s >= last_end:
            count += 1
            last_end = e
    return count
