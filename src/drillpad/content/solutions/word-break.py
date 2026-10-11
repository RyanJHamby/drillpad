# ruff: noqa
def word_break(s, word_dict):
    words = set(word_dict)
    lengths = sorted({len(w) for w in words})
    n = len(s)
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(1, n + 1):
        for L in lengths:
            if L > i:
                break
            if ok[i - L] and s[i - L:i] in words:
                ok[i] = True
                break
    return ok[n]
