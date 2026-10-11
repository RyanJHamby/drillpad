# ruff: noqa
def character_replacement(s, k):
    cnt = {}
    l = 0
    mx = 0
    best = 0
    for r, ch in enumerate(s):
        cnt[ch] = cnt.get(ch, 0) + 1
        mx = max(mx, cnt[ch])
        while (r - l + 1) - mx > k:
            cnt[s[l]] -= 1
            l += 1
        best = max(best, r - l + 1)
    return best
