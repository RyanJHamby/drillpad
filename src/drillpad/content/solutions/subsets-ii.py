# ruff: noqa
def subsets_with_dup(nums):
    nums = sorted(nums)
    res, path = [], []
    def go(start):
        res.append(path[:])
        for i in range(start, len(nums)):
            if i > start and nums[i] == nums[i - 1]:
                continue
            path.append(nums[i])
            go(i + 1)
            path.pop()
    go(0)
    return res
