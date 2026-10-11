# ruff: noqa
# gen
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        j = seen.get(target - x)
        if j is not None:
            return [j, i]
        seen[x] = i
