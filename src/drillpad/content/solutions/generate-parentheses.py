# ruff: noqa
def generate_parenthesis(n):
    out = []
    cur = []

    def go(o, c):
        if o == n and c == n:
            out.append("".join(cur))
            return
        if o < n:
            cur.append("(")
            go(o + 1, c)
            cur.pop()
        if c < o:
            cur.append(")")
            go(o, c + 1)
            cur.pop()

    go(0, 0)
    return out
