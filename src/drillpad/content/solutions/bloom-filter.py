# ruff: noqa
import hashlib
import math


class BloomFilter:
    def __init__(self, capacity, error_rate=0.01):
        if capacity <= 0 or not (0 < error_rate < 1):
            raise ValueError("bad parameters")
        self.m = math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.k = max(1, round(self.m / capacity * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)

    def _positions(self, item):
        d = hashlib.blake2b(item.encode(), digest_size=16).digest()
        h1 = int.from_bytes(d[:8], "big")
        h2 = int.from_bytes(d[8:], "big") | 1   # odd step avoids degenerate cycles
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    def add(self, item):
        for p in self._positions(item):
            self.bits[p >> 3] |= 1 << (p & 7)

    def might_contain(self, item):
        return all(self.bits[p >> 3] & (1 << (p & 7)) for p in self._positions(item))

    def __contains__(self, item):
        return self.might_contain(item)

    def count_set_bits(self):
        return sum(bin(b).count("1") for b in self.bits)
