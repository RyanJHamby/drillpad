# ruff: noqa
import bisect


class InMemoryDB:
    def __init__(self):
        self.store = {}         # key -> field -> (value, set_ts, ttl | None)
        self.backup_ts = []     # sorted backup timestamps
        self.backups = {}       # ts -> {key: {field: (value, remaining | None)}}

    @staticmethod
    def _live(entry, at):
        _, set_ts, ttl = entry
        return ttl is None or at < set_ts + ttl

    def _fields(self, key, at):
        return {f: e for f, e in self.store.get(key, {}).items() if self._live(e, at)}

    def set_at(self, key, field, value, ts):
        self.store.setdefault(key, {})[field] = (value, ts, None)

    def set_at_with_ttl(self, key, field, value, ts, ttl):
        self.store.setdefault(key, {})[field] = (value, ts, ttl)

    def get_at(self, key, field, ts):
        e = self.store.get(key, {}).get(field)
        return e[0] if e is not None and self._live(e, ts) else None

    def delete_at(self, key, field, ts):
        e = self.store.get(key, {}).get(field)
        if e is None:
            return False
        del self.store[key][field]
        return self._live(e, ts)

    def scan_at(self, key, ts):
        f = self._fields(key, ts)
        return [f"{name}({f[name][0]})" for name in sorted(f)]

    def scan_by_prefix_at(self, key, prefix, ts):
        f = self._fields(key, ts)
        return [f"{name}({f[name][0]})" for name in sorted(f) if name.startswith(prefix)]

    def backup(self, ts):
        snap, count = {}, 0
        for key in self.store:
            live = self._fields(key, ts)
            if live:
                snap[key] = {
                    f: (v, None if ttl is None else set_ts + ttl - ts)
                    for f, (v, set_ts, ttl) in live.items()
                }
                count += len(live)
        if ts not in self.backups:
            bisect.insort(self.backup_ts, ts)
        self.backups[ts] = snap
        return count

    def restore(self, ts, target_ts):
        i = bisect.bisect_right(self.backup_ts, target_ts)
        if i == 0:
            return False
        snap = self.backups[self.backup_ts[i - 1]]
        # remaining TTL is preserved relative to the restore moment
        self.store = {
            key: {f: (v, ts, rem) for f, (v, rem) in fields.items()}
            for key, fields in snap.items()
        }
        return True
