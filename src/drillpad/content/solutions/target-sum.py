# ruff: noqa
def find_target_sum_ways(nums, target):
    total = sum(nums)
    if abs(target) > total or (total + target) % 2:
        return 0
    s = (total + target) // 2
    ways = [1] + [0] * s
    for x in nums:
        for j in range(s, x - 1, -1):
            ways[j] += ways[j - x]
    return ways[s]
