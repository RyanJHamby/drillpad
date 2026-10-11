# ruff: noqa
def _clean(s):
    if not isinstance(s, str):
        return None
    d = s.replace(" ", "").replace("-", "")
    return d if d.isascii() and d.isdigit() else None


def _sum(digits, offset):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if (i + offset) % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total


def luhn_valid(s):
    d = _clean(s)
    if d is None or not 12 <= len(d) <= 19:
        return False
    return _sum(d, 0) % 10 == 0


def luhn_check_digit(payload):
    if not isinstance(payload, str) or not payload or not (payload.isascii() and payload.isdigit()):
        raise ValueError("payload must be digits")
    return (10 - _sum(payload, 1) % 10) % 10


def card_brand(s):
    if not luhn_valid(s):
        return "invalid"
    d = _clean(s)
    n = len(d)
    if d[0] == "4" and n in (13, 16, 19):
        return "visa"
    if n == 16 and (51 <= int(d[:2]) <= 55 or 2221 <= int(d[:4]) <= 2720):
        return "mastercard"
    if n == 15 and d[:2] in ("34", "37"):
        return "amex"
    if n == 16 and (d[:4] == "6011" or d[:2] == "65" or 644 <= int(d[:3]) <= 649):
        return "discover"
    return "unknown"
