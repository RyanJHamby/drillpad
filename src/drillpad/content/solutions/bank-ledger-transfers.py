# ruff: noqa
class Bank:
    def __init__(self):
        self.balances = {}
        self.entries = {}      # account -> [(delta, counterparty)]
        self.processed = {}    # txn_id -> status

    def create_account(self, account_id):
        if account_id in self.balances:
            return False
        self.balances[account_id] = 0
        self.entries[account_id] = []
        return True

    def deposit(self, account_id, amount):
        if account_id not in self.balances or not isinstance(amount, int) or amount <= 0:
            return None
        self.balances[account_id] += amount
        self.entries[account_id].append((amount, None))
        return self.balances[account_id]

    def transfer(self, src, dst, amount, txn_id=None):
        if txn_id is not None and txn_id in self.processed:
            return self.processed[txn_id]
        if (src not in self.balances or dst not in self.balances or src == dst
                or not isinstance(amount, int) or amount <= 0):
            status = "invalid"
        elif self.balances[src] < amount:
            status = "insufficient_funds"
        else:
            self.balances[src] -= amount
            self.balances[dst] += amount
            self.entries[src].append((-amount, dst))   # both legs recorded together
            self.entries[dst].append((amount, src))
            status = "ok"
        if txn_id is not None:
            self.processed[txn_id] = status
        return status

    def balance(self, account_id):
        return self.balances.get(account_id)

    def history(self, account_id):
        return list(self.entries.get(account_id, []))

    def total(self):
        return sum(self.balances.values())
