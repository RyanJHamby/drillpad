# ruff: noqa
from fractions import Fraction


def _rhu(num, den):
    return (2 * num + den) // (2 * den)


def accrued_interest(balance, annual_bps, days, basis=365):
    for v in (balance, annual_bps, days):
        if type(v) is not int or v < 0:
            raise ValueError("bad argument")
    if basis not in (360, 365):
        raise ValueError("basis must be 360 or 365")
    return _rhu(balance * annual_bps * days, 10000 * basis)


def amortization_schedule(principal, annual_bps, months):
    if type(principal) is not int or principal <= 0 or type(months) is not int or months < 1 \
            or type(annual_bps) is not int or annual_bps < 0:
        raise ValueError("bad loan")
    if annual_bps == 0:
        pmt = _rhu(principal, months)
    else:
        r = Fraction(annual_bps, 120000)
        f = principal * r / (1 - (1 + r) ** -months)
        pmt = _rhu(f.numerator, f.denominator)
    rows = []
    bal = principal
    for m in range(months):
        interest = _rhu(bal * annual_bps, 120000)
        owed = bal + interest
        pay = owed if m == months - 1 else min(pmt, owed)
        princ = pay - interest
        bal -= princ
        rows.append((pay, interest, princ, bal))
    return rows


def total_interest(schedule):
    return sum(row[1] for row in schedule)
