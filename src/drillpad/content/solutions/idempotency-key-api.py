# ruff: noqa
class IdempotencyConflict(Exception):
    pass


class InFlightError(Exception):
    pass


class PaymentAPI:
    def __init__(self, balances, charge_hook=None, key_ttl=86400):
        self.balances = dict(balances)
        self.hook = charge_hook
        self.ttl = key_ttl
        self.keys = {}
        self.counter = 0

    def balance(self, account):
        return self.balances[account]

    def create_payment(self, key, account, amount, now):
        if type(amount) is not int or amount <= 0 or account not in self.balances:
            raise ValueError("invalid payment request")
        rec = self.keys.get(key)
        if rec is not None and now - rec["first"] >= self.ttl:
            del self.keys[key]
            rec = None
        fp = (account, amount)
        if rec is not None:
            if rec["fp"] != fp:
                raise IdempotencyConflict(key)
            if rec["resp"] is None:
                raise InFlightError(key)
            return dict(rec["resp"])
        rec = {"fp": fp, "resp": None, "first": now}
        self.keys[key] = rec
        try:
            if self.hook is not None:
                self.hook(account, amount)
        except BaseException:
            del self.keys[key]
            raise
        self.counter += 1
        if self.balances[account] >= amount:
            self.balances[account] -= amount
            status = "succeeded"
        else:
            status = "declined"
        rec["resp"] = {"payment_id": "pay_%d" % self.counter, "status": status, "account": account, "amount": amount}
        return dict(rec["resp"])
