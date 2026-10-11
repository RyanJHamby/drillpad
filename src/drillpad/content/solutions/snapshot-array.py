# ruff: noqa
import bisect


class SnapshotArray:
    def __init__(self, length):
        self.length = length
        self.snap_id = 0
        # per index: parallel lists of snapshot ids and values (only for indexes ever set)
        self.ids = {}
        self.vals = {}

    def set(self, index, val):
        if not 0 <= index < self.length:
            raise IndexError(index)
        ids = self.ids.setdefault(index, [])
        vals = self.vals.setdefault(index, [])
        if ids and ids[-1] == self.snap_id:
            vals[-1] = val
        else:
            ids.append(self.snap_id)
            vals.append(val)

    def snap(self):
        self.snap_id += 1
        return self.snap_id - 1

    def get(self, index, snap_id):
        if not 0 <= index < self.length:
            raise IndexError(index)
        if not 0 <= snap_id < self.snap_id:
            raise ValueError(snap_id)
        ids = self.ids.get(index)
        if not ids:
            return 0
        i = bisect.bisect_right(ids, snap_id) - 1
        return self.vals[index][i] if i >= 0 else 0
