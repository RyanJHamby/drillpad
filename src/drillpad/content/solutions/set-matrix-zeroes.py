# ruff: noqa
def set_zeroes(matrix):
    if not matrix:
        return None
    rows = set()
    cols = set()
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v == 0:
                rows.add(i)
                cols.add(j)
    for i, row in enumerate(matrix):
        for j in range(len(row)):
            if i in rows or j in cols:
                row[j] = 0
    return None
