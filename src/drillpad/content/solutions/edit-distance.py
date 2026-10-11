# ruff: noqa
def min_distance(word1, word2):
    n = len(word2)
    prev = list(range(n + 1))
    for i in range(1, len(word1) + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                cur[j] = prev[j - 1]
            else:
                cur[j] = 1 + min(prev[j], cur[j - 1], prev[j - 1])
        prev = cur
    return prev[n]
