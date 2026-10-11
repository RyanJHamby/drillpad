# ruff: noqa
def max_profit_cooldown(prices):
    hold = float("-inf")
    sold = rest = 0
    for p in prices:
        prev_sold = sold
        sold = hold + p
        hold = max(hold, rest - p)
        rest = max(rest, prev_sold)
    return max(sold, rest)
