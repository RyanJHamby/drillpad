# ruff: noqa
def max_profit(k, prices):
    if k < 0:
        raise ValueError("k must be non-negative")
    n = len(prices)
    if k == 0 or n < 2:
        return 0
    if k >= n // 2:
        return sum(max(0, b - a) for a, b in zip(prices, prices[1:]))
    buy = [float("-inf")] * (k + 1)
    sell = [0] * (k + 1)
    for p in prices:
        for j in range(1, k + 1):
            buy[j] = max(buy[j], sell[j - 1] - p)
            sell[j] = max(sell[j], buy[j] + p)
    return sell[k]
