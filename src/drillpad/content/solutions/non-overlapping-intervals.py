# ruff: noqa
def erase_overlap_intervals(intervals):
    if not intervals:
        return 0
    ivs = sorted(intervals, key=lambda x: x[1])
    end = ivs[0][1]
    removed = 0
    for s, e in ivs[1:]:
        if s >= end:
            end = e
        else:
            removed += 1
    return removed
