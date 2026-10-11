# ruff: noqa
from bisect import bisect_left


class FeeSchedule:
    def __init__(self, tiers, mode="marginal", fixed=0, min_fee=0, max_fee=None):
        if mode not in ("marginal", "volume") or not tiers:
            raise ValueError("bad mode or tiers")
        if fixed < 0 or min_fee < 0 or (max_fee is not None and max_fee < min_fee):
            raise ValueError("bad fee bounds")
        prev = 0
        self.bounds = []
        self.rates = []
        self.cum = []
        acc = 0
        for i, (up, bps) in enumerate(tiers):
            if bps < 0:
                raise ValueError("negative rate")
            last = i == len(tiers) - 1
            if last != (up is None):
                raise ValueError("only the last tier may (and must) be unbounded")
            self.cum.append(acc)
            self.rates.append(bps)
            if not last:
                if up <= prev:
                    raise ValueError("tier bounds must strictly increase from > 0")
                acc += (up - prev) * bps
                self.bounds.append(up)
                prev = up
        self.starts = [0] + self.bounds
        self.mode = mode
        self.fixed = fixed
        self.min_fee = min_fee
        self.max_fee = max_fee

    def fee(self, amount):
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive int")
        i = bisect_left(self.bounds, amount)
        if self.mode == "marginal":
            num = self.cum[i] + (amount - self.starts[i]) * self.rates[i]
        else:
            num = amount * self.rates[i]
        fee = (2 * num + 10000) // 20000 + self.fixed
        fee = max(fee, self.min_fee)
        if self.max_fee is not None:
            fee = min(fee, self.max_fee)
        return fee
