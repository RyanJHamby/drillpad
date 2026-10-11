# ruff: noqa
FLAGS = {"IOC": 1, "FOK": 2, "POST_ONLY": 4, "HIDDEN": 8, "REDUCE_ONLY": 16}
_NAMES = sorted(FLAGS, key=FLAGS.get)
_ALL = 31


def parse_flags(names):
    f = 0
    for n in names:
        if n not in FLAGS:
            raise ValueError("unknown flag " + str(n))
        f |= FLAGS[n]
    return f


def flag_names(flags):
    return [n for n in _NAMES if flags & FLAGS[n]]


def toggle(flags, name):
    if name not in FLAGS:
        raise ValueError("unknown flag")
    return flags ^ FLAGS[name]


def validate(flags):
    if not isinstance(flags, int) or flags < 0 or flags & ~_ALL:
        return False
    if flags & FLAGS["IOC"] and flags & FLAGS["FOK"]:
        return False
    if flags & FLAGS["POST_ONLY"] and flags & (FLAGS["IOC"] | FLAGS["FOK"]):
        return False
    return True


def popcount(x):
    if x < 0:
        raise ValueError("x must be non-negative")
    c = 0
    while x:
        x &= x - 1
        c += 1
    return c


def lowest_set_bit(x):
    if x < 0:
        raise ValueError("x must be non-negative")
    if x == 0:
        return -1
    return (x & -x).bit_length() - 1


def diff_flags(a, b):
    return flag_names(a ^ b)


def pack(side, flags, qty):
    if side not in ("buy", "sell") or not validate(flags) or not isinstance(qty, int) or not 0 < qty < (1 << 32):
        raise ValueError("bad order")
    return (qty << 8) | (flags << 1) | (1 if side == "sell" else 0)


def unpack(word):
    if not isinstance(word, int) or word < 0 or word >> 40 or word & 0xC0:
        raise ValueError("bad word")
    return ("sell" if word & 1 else "buy", (word >> 1) & _ALL, word >> 8)
