# ruff: noqa
def merge_triplets(triplets, target):
    hit = [False] * 3
    for t in triplets:
        if t[0] <= target[0] and t[1] <= target[1] and t[2] <= target[2]:
            for k in range(3):
                if t[k] == target[k]:
                    hit[k] = True
    return all(hit)
