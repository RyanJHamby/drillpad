# ruff: noqa
def permute(nums):
    n = len(nums)
    res, path, used = [], [], [False] * n
    def go():
        if len(path) == n:
            res.append(path[:])
            return
        for i in range(n):
            if used[i]:
                continue
            used[i] = True
            path.append(nums[i])
            go()
            path.pop()
            used[i] = False
    go()
    return res
