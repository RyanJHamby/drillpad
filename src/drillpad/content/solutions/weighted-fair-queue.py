# ruff: noqa
import heapq
from fractions import Fraction


class WFQ:
    def __init__(self):
        self.weight = {}
        self.last_finish = {}
        self.backlog_count = {}
        self.vtime = Fraction(0)
        self.heap = []
        self.seq = 0

    def add_flow(self, flow, weight):
        if weight <= 0:
            raise ValueError("weight must be positive")
        self.weight[flow] = weight
        self.last_finish.setdefault(flow, Fraction(0))
        self.backlog_count.setdefault(flow, 0)

    def enqueue(self, flow, packet_id, size):
        if flow not in self.weight:
            raise KeyError(flow)
        if size <= 0:
            raise ValueError("size must be positive")
        start = max(self.vtime, self.last_finish[flow])
        finish = start + Fraction(size, 1) / self.weight[flow]
        self.last_finish[flow] = finish
        self.backlog_count[flow] += 1
        heapq.heappush(self.heap, (finish, self.seq, flow, packet_id))
        self.seq += 1

    def dequeue(self):
        if not self.heap:
            return None
        finish, _, flow, packet_id = heapq.heappop(self.heap)
        self.vtime = finish
        self.backlog_count[flow] -= 1
        return packet_id

    def backlog(self, flow):
        return self.backlog_count[flow]
