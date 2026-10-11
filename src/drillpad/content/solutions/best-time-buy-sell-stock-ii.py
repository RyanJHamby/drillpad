# ruff: noqa
def max_profit(prices, fee=0):
    if fee < 0:
        raise ValueError("fee must be non-negative")
    if not prices:
        return 0
    cash, hold = 0, -prices[0]
    for p in prices[1:]:
        cash, hold = max(cash, hold + p - fee), max(hold, cash - p)
    return cash
