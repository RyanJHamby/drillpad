# ruff: noqa
def is_match(s, p):
    m, n = len(s), len(p)
    ok = [[False] * (n + 1) for _ in range(m + 1)]
    ok[0][0] = True
    for j in range(2, n + 1):
        if p[j - 1] == "*":
            ok[0][j] = ok[0][j - 2]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if p[j - 1] == "*":
                ok[i][j] = ok[i][j - 2] or (
                    p[j - 2] in (".", s[i - 1]) and ok[i - 1][j]
                )
            else:
                ok[i][j] = p[j - 1] in (".", s[i - 1]) and ok[i - 1][j - 1]
    return ok[m][n]
