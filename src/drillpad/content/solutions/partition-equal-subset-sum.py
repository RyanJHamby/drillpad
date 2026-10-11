# ruff: noqa
def can_partition(nums):
    total = sum(nums)
    if total % 2:
        return False
    half = total // 2
    bits = 1
    for x in nums:
        bits |= bits << x
    return bool((bits >> half) & 1)
