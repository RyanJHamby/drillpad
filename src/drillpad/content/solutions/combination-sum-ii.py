# ruff: noqa
def combination_sum2(candidates, target):
    cs = sorted(candidates)
    res, path = [], []
    def go(start, rem):
        if rem == 0:
            res.append(path[:])
            return
        for i in range(start, len(cs)):
            if i > start and cs[i] == cs[i - 1]:
                continue
            if cs[i] > rem:
                break
            path.append(cs[i])
            go(i + 1, rem - cs[i])
            path.pop()
    go(0, target)
    return res
