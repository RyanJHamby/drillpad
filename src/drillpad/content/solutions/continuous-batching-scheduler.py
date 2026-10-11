# ruff: noqa
from collections import deque


class ContinuousBatcher:
    def __init__(self, max_slots, kv_budget):
        if max_slots < 1 or kv_budget < 1:
            raise ValueError("max_slots and kv_budget must be >= 1")
        self.max_slots, self.kv_budget = max_slots, kv_budget
        self.waiting = deque()          # (id, remaining, reserved)
        self.active = []                # [id, remaining, reserved] in admission order
        self.reserved = 0
        self.steps = 0
        self.seen = set()

    def submit(self, req_id, prompt_len, max_new):
        if req_id in self.seen:
            raise ValueError("duplicate id")
        if prompt_len < 0 or max_new < 1 or prompt_len + max_new > self.kv_budget:
            raise ValueError("bad request")
        self.seen.add(req_id)
        self.waiting.append((req_id, max_new, prompt_len + max_new))

    def step(self):
        self.steps += 1
        while (self.waiting and len(self.active) < self.max_slots
               and self.reserved + self.waiting[0][2] <= self.kv_budget):
            rid, rem, res = self.waiting.popleft()
            self.active.append([rid, rem, res])
            self.reserved += res
        done, keep = [], []
        for seq in self.active:
            seq[1] -= 1
            if seq[1] == 0:
                done.append(seq[0])
                self.reserved -= seq[2]
            else:
                keep.append(seq)
        self.active = keep
        return done

    def active_ids(self):
        return [s[0] for s in self.active]

    def waiting_ids(self):
        return [w[0] for w in self.waiting]

    def kv_used(self):
        return self.reserved

    def run_until_drained(self):
        out = {}
        while self.active or self.waiting:
            for rid in self.step():
                out[rid] = self.steps
        return out
