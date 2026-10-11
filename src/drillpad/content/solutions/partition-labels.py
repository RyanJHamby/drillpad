# ruff: noqa
def partition_labels(s):
    last = {c: i for i, c in enumerate(s)}
    out = []
    start = end = 0
    for i, c in enumerate(s):
        end = max(end, last[c])
        if i == end:
            out.append(i - start + 1)
            start = i + 1
    return out
