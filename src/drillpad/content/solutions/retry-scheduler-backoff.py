# ruff: noqa
import heapq

PERMANENT_ERRORS = {"INVALID_CREDENTIALS", "ACCOUNT_CLOSED", "ITEM_LOGIN_REQUIRED"}


class RetryScheduler:
    def __init__(self, base_delay=1, max_delay=60, max_retries=5):
        self.base, self.cap, self.max_retries = base_delay, max_delay, max_retries
        self.heap = []                     # (due_time, request_id)
        self.state = {}                    # id -> status
        self.failures = {}                 # id -> failures so far

    def submit(self, request_id, now):
        if request_id in self.state:
            raise ValueError("duplicate request id")
        self.state[request_id] = "scheduled"
        self.failures[request_id] = 0
        heapq.heappush(self.heap, (now, request_id))

    def due(self, now):
        out = []
        while self.heap and self.heap[0][0] <= now:
            _, rid = heapq.heappop(self.heap)
            self.state[rid] = "in_flight"
            out.append(rid)
        return out

    def report(self, request_id, now, ok, error_code=None):
        if self.state.get(request_id) != "in_flight":
            raise ValueError("request is not in flight")
        if ok:
            self.state[request_id] = "succeeded"
            return "succeeded"
        if error_code in PERMANENT_ERRORS:
            self.state[request_id] = "failed_permanent"
            return "failed_permanent"
        self.failures[request_id] += 1
        f = self.failures[request_id]
        if f > self.max_retries:
            self.state[request_id] = "failed_exhausted"
            return "failed_exhausted"
        delay = min(self.base * 2 ** (f - 1), self.cap)
        heapq.heappush(self.heap, (now + delay, request_id))
        self.state[request_id] = "scheduled"
        return "retry"

    def status(self, request_id):
        return self.state.get(request_id)

    def next_due_time(self):
        return self.heap[0][0] if self.heap else None
