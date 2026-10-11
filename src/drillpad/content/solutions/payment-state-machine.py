# ruff: noqa
class PaymentError(Exception):
    pass


class PaymentProcessor:
    def __init__(self, auth_ttl=604800):
        self.ttl = auth_ttl
        self.p = {}

    def _get(self, pid, now):
        if pid not in self.p:
            raise PaymentError("unknown payment")
        r = self.p[pid]
        if r["state"] == "AUTHORIZED" and now - r["at"] >= self.ttl:
            r["state"] = "EXPIRED"
        return r

    def authorize(self, pid, amount, now):
        if amount <= 0 or pid in self.p:
            raise PaymentError("bad authorize")
        self.p[pid] = {"state": "AUTHORIZED", "auth": amount, "cap": 0, "ref": 0, "at": now, "rids": set()}
        return "AUTHORIZED"

    def capture(self, pid, now, amount=None):
        r = self._get(pid, now)
        if r["state"] != "AUTHORIZED":
            raise PaymentError("cannot capture from " + r["state"])
        amt = r["auth"] if amount is None else amount
        if amt <= 0 or amt > r["auth"]:
            raise PaymentError("bad capture amount")
        r["cap"] = amt
        r["state"] = "CAPTURED"
        return "CAPTURED"

    def void(self, pid, now):
        r = self._get(pid, now)
        if r["state"] != "AUTHORIZED":
            raise PaymentError("cannot void from " + r["state"])
        r["state"] = "VOIDED"
        return "VOIDED"

    def refund(self, pid, amount, now, refund_id=None):
        r = self._get(pid, now)
        if refund_id is not None and refund_id in r["rids"]:
            return r["state"]
        if r["state"] not in ("CAPTURED", "PARTIALLY_REFUNDED"):
            raise PaymentError("cannot refund from " + r["state"])
        if amount <= 0 or r["ref"] + amount > r["cap"]:
            raise PaymentError("bad refund amount")
        r["ref"] += amount
        r["state"] = "REFUNDED" if r["ref"] == r["cap"] else "PARTIALLY_REFUNDED"
        if refund_id is not None:
            r["rids"].add(refund_id)
        return r["state"]

    def summary(self, pid, now):
        r = self._get(pid, now)
        return {"state": r["state"], "authorized": r["auth"], "captured": r["cap"], "refunded": r["ref"]}
