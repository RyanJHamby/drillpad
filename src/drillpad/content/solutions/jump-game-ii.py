# ruff: noqa
def min_jumps(nums):
    jumps = cur_end = far = 0
    for i in range(len(nums) - 1):
        far = max(far, i + nums[i])
        if i == cur_end:
            jumps += 1
            cur_end = far
            if cur_end >= len(nums) - 1:
                break
    return jumps
