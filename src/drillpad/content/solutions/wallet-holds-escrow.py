# ruff: noqa
import heapq


class WalletError(Exception):
    pass


class Wallet:
    def __init__(self):
        self.bal = {}
        self.held = {}
        self.holds = {}      # id -> [account, amount, status]
        self.heap = []
        self.escrows = {}    # id -> [buyer, seller, amount, status]

    def _advance(self, now):
        while self.heap and self.heap[0][0] <= now:
            _, hid = heapq.heappop(self.heap)
            h = self.holds[hid]
            if h[2] == "ACTIVE":
                h[2] = "EXPIRED"
                self.held[h[0]] -= h[1]

    def deposit(self, account, amount):
        if amount <= 0:
            raise WalletError("bad amount")
        self.bal[account] = self.bal.get(account, 0) + amount
        return self.bal[account]

    def balance(self, account):
        return self.bal.get(account, 0)

    def available(self, account, now):
        self._advance(now)
        return self.bal.get(account, 0) - self.held.get(account, 0)

    def hold(self, account, hold_id, amount, now, ttl=None):
        self._advance(now)
        if amount <= 0 or hold_id in self.holds or self.available(account, now) < amount:
            raise WalletError("cannot hold")
        self.holds[hold_id] = [account, amount, "ACTIVE"]
        self.held[account] = self.held.get(account, 0) + amount
        if ttl is not None:
            heapq.heappush(self.heap, (now + ttl, hold_id))
        return True

    def capture_hold(self, hold_id, now, amount=None):
        self._advance(now)
        h = self.holds.get(hold_id)
        if h is None or h[2] != "ACTIVE":
            raise WalletError("hold not active")
        amt = h[1] if amount is None else amount
        if amt <= 0 or amt > h[1]:
            raise WalletError("bad capture amount")
        self.held[h[0]] -= h[1]
        self.bal[h[0]] -= amt
        h[2] = "CAPTURED"
        return amt

    def release_hold(self, hold_id, now):
        self._advance(now)
        h = self.holds.get(hold_id)
        if h is None:
            raise WalletError("unknown hold")
        if h[2] != "ACTIVE":
            return False
        self.held[h[0]] -= h[1]
        h[2] = "RELEASED"
        return True

    def open_escrow(self, escrow_id, buyer, seller, amount, now):
        if amount <= 0 or escrow_id in self.escrows or self.available(buyer, now) < amount:
            raise WalletError("cannot open escrow")
        self.bal[buyer] -= amount
        self.escrows[escrow_id] = [buyer, seller, amount, "OPEN"]

    def _resolve(self, escrow_id, to_seller):
        e = self.escrows.get(escrow_id)
        if e is None or e[3] != "OPEN":
            raise WalletError("escrow not open")
        who = e[1] if to_seller else e[0]
        self.bal[who] = self.bal.get(who, 0) + e[2]
        e[3] = "SETTLED" if to_seller else "REFUNDED"

    def settle_escrow(self, escrow_id):
        self._resolve(escrow_id, True)

    def refund_escrow(self, escrow_id):
        self._resolve(escrow_id, False)

    def total_funds(self):
        return sum(self.bal.values()) + sum(e[2] for e in self.escrows.values() if e[3] == "OPEN")
