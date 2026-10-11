# ruff: noqa
def insert_interval(intervals, new):
    out = []
    i, n = 0, len(intervals)
    s, e = new
    while i < n and intervals[i][1] < s:
        out.append(list(intervals[i]))
        i += 1
    while i < n and intervals[i][0] <= e:
        s = min(s, intervals[i][0])
        e = max(e, intervals[i][1])
        i += 1
    out.append([s, e])
    while i < n:
        out.append(list(intervals[i]))
        i += 1
    return out
