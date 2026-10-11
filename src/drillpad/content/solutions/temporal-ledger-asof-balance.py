# ruff: noqa
from bisect import bisect_right, bisect_left


class Ledger:
    def __init__(self):
        self.acc = {}      # account -> dict(keys=[(ts, seq)], amounts=[...], ids=[...], pref=[0,...], dirty=bool)
        self.index = {}    # entry_id -> (account, key)
        self.seq = 0

    def _a(self, account):
        a = self.acc.get(account)
        if a is None:
            a = self.acc[account] = {"keys": [], "amt": [], "ids": [], "pref": [0], "dirty": False}
        return a

    def post(self, account, amount, ts, entry_id):
        if entry_id in self.index:
            return False
        self.seq += 1
        key = (ts, self.seq)
        a = self._a(account)
        keys = a["keys"]
        if not keys or key > keys[-1]:
            keys.append(key)
            a["amt"].append(amount)
            a["ids"].append(entry_id)
            if not a["dirty"]:
                a["pref"].append(a["pref"][-1] + amount)
        else:
            i = bisect_right(keys, key)
            keys.insert(i, key)
            a["amt"].insert(i, amount)
            a["ids"].insert(i, entry_id)
            a["dirty"] = True
        self.index[entry_id] = (account, key)
        return True

    def void(self, entry_id):
        if entry_id not in self.index:
            return False
        account, key = self.index.pop(entry_id)
        a = self.acc[account]
        i = bisect_left(a["keys"], key)
        del a["keys"][i], a["amt"][i], a["ids"][i]
        a["dirty"] = True
        return True

    def _prefix(self, a):
        if a["dirty"]:
            p = [0]
            for x in a["amt"]:
                p.append(p[-1] + x)
            a["pref"] = p
            a["dirty"] = False
        return a["pref"]

    def balance_as_of(self, account, ts):
        a = self.acc.get(account)
        if a is None:
            return 0
        pref = self._prefix(a)
        i = bisect_right(a["keys"], (ts, float("inf")))
        return pref[i]

    def net_change(self, account, start, end):
        if end < start:
            raise ValueError("end before start")
        return self.balance_as_of(account, end) - self.balance_as_of(account, start)
