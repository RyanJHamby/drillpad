# ruff: noqa
def solve_n_queens(n):
    res = []
    cols, d1, d2 = set(), set(), set()
    pos = []
    def go(r):
        if r == n:
            res.append(["." * c + "Q" + "." * (n - c - 1) for c in pos])
            return
        for c in range(n):
            if c in cols or (r - c) in d1 or (r + c) in d2:
                continue
            cols.add(c); d1.add(r - c); d2.add(r + c)
            pos.append(c)
            go(r + 1)
            pos.pop()
            cols.discard(c); d1.discard(r - c); d2.discard(r + c)
    go(0)
    return res
