# ruff: noqa
import heapq


class PagedKVCache:
    def __init__(self, num_blocks, block_size):
        if num_blocks < 0 or block_size < 1:
            raise ValueError("bad geometry")
        self.bs = block_size
        self.pool = list(range(num_blocks))
        heapq.heapify(self.pool)
        self.ref = {}
        self.tables = {}
        self.tokens = {}

    def num_free(self):
        return len(self.pool)

    def refcount(self, block):
        return self.ref.get(block, 0)

    def block_table(self, seq_id):
        return list(self.tables[seq_id])

    def num_tokens(self, seq_id):
        return self.tokens[seq_id]

    def _take(self):
        b = heapq.heappop(self.pool)
        self.ref[b] = 1
        return b

    def _drop(self, b):
        self.ref[b] -= 1
        if self.ref[b] == 0:
            del self.ref[b]
            heapq.heappush(self.pool, b)
            return 1
        return 0

    def allocate(self, seq_id, num_tokens):
        if seq_id in self.tables:
            raise ValueError("duplicate sequence")
        if num_tokens < 0:
            raise ValueError("negative tokens")
        need = -(-num_tokens // self.bs)
        if need > len(self.pool):
            raise MemoryError("out of blocks")
        self.tables[seq_id] = [self._take() for _ in range(need)]
        self.tokens[seq_id] = num_tokens
        return list(self.tables[seq_id])

    def append(self, seq_id, n=1):
        table = self.tables[seq_id]
        if n < 0:
            raise ValueError("negative n")
        t = self.tokens[seq_id]
        new_total = -(-(t + n) // self.bs)
        cow = n > 0 and t % self.bs != 0 and self.ref[table[-1]] > 1
        need = (new_total - len(table)) + (1 if cow else 0)
        if need > len(self.pool):
            raise MemoryError("out of blocks")
        new = []
        if cow:
            old = table[-1]
            nb = self._take()
            self._drop(old)
            table[-1] = nb
            new.append(nb)
        while len(table) < new_total:
            nb = self._take()
            table.append(nb)
            new.append(nb)
        self.tokens[seq_id] = t + n
        return new

    def fork(self, parent, child):
        if child in self.tables:
            raise ValueError("duplicate sequence")
        table = self.tables[parent]
        for b in table:
            self.ref[b] += 1
        self.tables[child] = list(table)
        self.tokens[child] = self.tokens[parent]

    def free(self, seq_id):
        table = self.tables.pop(seq_id)
        del self.tokens[seq_id]
        return sum(self._drop(b) for b in table)
