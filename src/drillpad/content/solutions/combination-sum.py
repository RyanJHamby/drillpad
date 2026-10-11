# ruff: noqa
# gen
def combination_sum(candidates, target):
    cands = sorted(candidates)
    res, cur = [], []
    def go(start, rem):
        if rem == 0:
            res.append(cur[:])
            return
        for i in range(start, len(cands)):
            if cands[i] > rem:
                break
            cur.append(cands[i])
            go(i, rem - cands[i])
            cur.pop()
    go(0, target)
    return res
