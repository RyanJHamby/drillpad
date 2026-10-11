# ruff: noqa
def reconcile(ledger, statement, tolerance_days=0):
    if tolerance_days < 0:
        raise ValueError("tolerance_days must be >= 0")
    for lst in (ledger, statement):
        if len({x["id"] for x in lst}) != len(lst):
            raise ValueError("duplicate id")
    lg, sg = {}, {}
    for i, x in enumerate(ledger):
        lg.setdefault(x["amount"], []).append((x["date"], i))
    for j, x in enumerate(statement):
        sg.setdefault(x["amount"], []).append((x["date"], j))
    pairs = []
    used_l, used_s = set(), set()
    for amount, ls in lg.items():
        ss = sg.get(amount)
        if not ss:
            continue
        ls.sort()
        ss.sort()
        i = j = 0
        while i < len(ls) and j < len(ss):
            if abs(ls[i][0] - ss[j][0]) <= tolerance_days:
                pairs.append((ls[i][1], ss[j][1]))
                used_l.add(ls[i][1])
                used_s.add(ss[j][1])
                i += 1
                j += 1
            elif ls[i][0] < ss[j][0]:
                i += 1
            else:
                j += 1
    pairs.sort()
    return {
        "matched": [(ledger[a]["id"], statement[b]["id"]) for a, b in pairs],
        "unmatched_ledger": [x["id"] for i, x in enumerate(ledger) if i not in used_l],
        "unmatched_statement": [x["id"] for j, x in enumerate(statement) if j not in used_s],
    }
