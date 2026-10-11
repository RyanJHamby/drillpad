# ruff: noqa
# gen
def subarray_sum(nums, k):
    seen = {0: 1}
    s = ans = 0
    for x in nums:
        s += x
        ans += seen.get(s - k, 0)
        seen[s] = seen.get(s, 0) + 1
    return ans
