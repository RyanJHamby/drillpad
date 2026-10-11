# ruff: noqa
def subsets(nums):
    res, path = [], []
    def go(start):
        res.append(path[:])
        for i in range(start, len(nums)):
            path.append(nums[i])
            go(i + 1)
            path.pop()
    go(0)
    return res
