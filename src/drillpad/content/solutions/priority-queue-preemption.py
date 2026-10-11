# ruff: noqa
import heapq


class PreemptiveScheduler:
    def __init__(self, slots):
        if slots < 1:
            raise ValueError("slots")
        self.slots = slots
        self.seq = 0
        self.info = {}              # id -> [priority, seq, remaining, preemptions]
        self.waiting = []           # min-heap of (priority, seq, id)
        self.running = []           # max-heap via negation: (-priority, -seq, id)

    def submit(self, job_id, priority, work):
        if job_id in self.info or work < 1:
            raise ValueError("bad job")
        self.info[job_id] = [priority, self.seq, work, 0]
        heapq.heappush(self.waiting, (priority, self.seq, job_id))
        self.seq += 1

    def _select(self):
        while self.waiting and len(self.running) < self.slots:
            p, s, j = heapq.heappop(self.waiting)
            heapq.heappush(self.running, (-p, -s, j))
        while self.waiting and self.running and self.waiting[0][:2] < (-self.running[0][0], -self.running[0][1]):
            np_, ns, nj = heapq.heappop(self.waiting)
            op, os_, oj = heapq.heappop(self.running)
            self.info[oj][3] += 1
            heapq.heappush(self.waiting, (-op, -os_, oj))
            heapq.heappush(self.running, (-np_, -ns, nj))

    def tick(self):
        self._select()
        done = []
        keep = []
        for entry in self.running:
            j = entry[2]
            self.info[j][2] -= 1
            if self.info[j][2] == 0:
                done.append((self.info[j][0], self.info[j][1], j))
            else:
                keep.append(entry)
        if done:
            heapq.heapify(keep)
            self.running = keep
        done.sort()
        return [j for _, _, j in done]

    def running_ids(self):
        return [j for _, _, j in sorted((-p, -s, j) for p, s, j in self.running)]

    def waiting_ids(self):
        return [j for _, _, j in sorted(self.waiting)]

    def preemptions(self, job_id):
        return self.info[job_id][3]
