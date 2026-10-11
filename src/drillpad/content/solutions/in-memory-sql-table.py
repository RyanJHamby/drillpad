# ruff: noqa
import operator

OPS = {"=": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le,
       ">": operator.gt, ">=": operator.ge}


class Table:
    def __init__(self, columns):
        self.columns = list(columns)
        self.rows = {}          # id -> row dict (insertion ordered)
        self.next_id = 1
        self.indexes = {}       # column -> {value: set(ids)}
        self.last_scanned = 0

    def _check_col(self, c):
        if c not in self.columns:
            raise KeyError(c)

    def insert(self, row):
        if set(row) != set(self.columns):
            raise ValueError("row keys must equal columns")
        rid = self.next_id
        self.next_id += 1
        self.rows[rid] = dict(row)
        for c, idx in self.indexes.items():
            idx.setdefault(row[c], set()).add(rid)
        return rid

    def create_index(self, column):
        self._check_col(column)
        idx = {}
        for rid, row in self.rows.items():
            idx.setdefault(row[column], set()).add(rid)
        self.indexes[column] = idx

    def _match_ids(self, where):
        conds = list(where or [])
        for c, op, _ in conds:
            self._check_col(c)
            if op not in OPS:
                raise ValueError(op)
        candidates = None
        for c, op, v in conds:
            if op == "=" and c in self.indexes:
                bucket = self.indexes[c].get(v, set())
                if candidates is None or len(bucket) < len(candidates):
                    candidates = bucket
        ids = sorted(candidates) if candidates is not None else list(self.rows)
        self.last_scanned = len(ids)
        return [rid for rid in ids if all(OPS[op](self.rows[rid][c], v) for c, op, v in conds)]

    def select(self, where=None, order_by=None, desc=False, limit=None, columns=None):
        ids = self._match_ids(where)
        if order_by is not None:
            self._check_col(order_by)
            ids = sorted(ids, key=lambda r: self.rows[r][order_by], reverse=desc)   # sorted is stable, also reversed
        if limit is not None:
            ids = ids[:limit]
        cols = columns if columns is not None else self.columns
        for c in cols:
            self._check_col(c)
        return [{c: self.rows[r][c] for c in cols} for r in ids]

    def update(self, where, changes):
        for c in changes:
            self._check_col(c)
        ids = self._match_ids(where)
        for rid in ids:
            row = self.rows[rid]
            for c, v in changes.items():
                if c in self.indexes and row[c] != v:
                    self.indexes[c][row[c]].discard(rid)
                    if not self.indexes[c][row[c]]:
                        del self.indexes[c][row[c]]
                    self.indexes[c].setdefault(v, set()).add(rid)
                row[c] = v
        return len(ids)

    def delete(self, where):
        ids = self._match_ids(where)
        for rid in ids:
            row = self.rows.pop(rid)
            for c, idx in self.indexes.items():
                idx[row[c]].discard(rid)
                if not idx[row[c]]:
                    del idx[row[c]]
        return len(ids)
