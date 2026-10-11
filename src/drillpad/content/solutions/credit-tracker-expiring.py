# ruff: noqa
import heapq
import itertools


class CreditTracker:
    def __init__(self):
        self.heap = []                 # [end, seq, start, remaining], earliest expiry first
        self.seq = itertools.count()

    def add_credit(self, start, end, amount):
        if end <= start or amount <= 0:
            raise ValueError("bad credit")
        heapq.heappush(self.heap, [end, next(self.seq), start, amount])

    def _expire(self, now):
        while self.heap and self.heap[0][0] <= now:
            heapq.heappop(self.heap)

    def check_credit(self, now):
        self._expire(now)
        return sum(e[3] for e in self.heap if e[2] <= now)

    def subtract_credit(self, now, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._expire(now)
        touched, skipped, need = [], [], amount
        while need > 0 and self.heap:
            e = heapq.heappop(self.heap)
            if e[2] > now:                      # not started yet: unusable, keep it
                skipped.append(e)
                continue
            take = min(need, e[3])
            touched.append((e, e[3]))           # remember original remaining for rollback
            e[3] -= take
            need -= take
            if e[3] > 0:
                heapq.heappush(self.heap, e)
                break
        if need > 0:                            # insufficient: undo everything
            for e, rem in touched:
                e[3] = rem
                if e[3] > 0 and e not in self.heap:
                    heapq.heappush(self.heap, e)
            for e in skipped:
                heapq.heappush(self.heap, e)
            raise ValueError("insufficient credit")
        for e in skipped:
            heapq.heappush(self.heap, e)
