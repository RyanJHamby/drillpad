# ruff: noqa
def is_happy(n):
    seen = set()
    while n != 1:
        if n in seen or n <= 0:
            return False
        seen.add(n)
        s = 0
        while n:
            n, d = divmod(n, 10)
            s += d * d
        n = s
    return True
