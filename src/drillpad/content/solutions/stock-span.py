# ruff: noqa
class StockSpanner:
    def __init__(self):
        self.stack = []   # (price, span), prices strictly decreasing

    def next(self, price):
        if not isinstance(price, int) or price <= 0:
            raise ValueError("price must be a positive int")
        span = 1
        while self.stack and self.stack[-1][0] <= price:
            span += self.stack.pop()[1]
        self.stack.append((price, span))
        return span
