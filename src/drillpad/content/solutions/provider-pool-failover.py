# ruff: noqa
class AllProvidersDown(RuntimeError):
    pass


class ProviderPool:
    def __init__(self, providers, max_fails=3, cooldown=30.0):
        self.names = list(providers)               # priority order
        self.max_fails, self.cooldown = max_fails, cooldown
        self.fails = {n: 0 for n in self.names}
        self.down_until = {n: 0.0 for n in self.names}

    def healthy(self, now):
        return [n for n in self.names if now >= self.down_until[n]]

    def _report(self, name, ok, now):
        if ok:
            self.fails[name] = 0
            return
        self.fails[name] += 1
        if self.fails[name] >= self.max_fails:
            self.down_until[name] = now + self.cooldown
            self.fails[name] = 0

    def call(self, request, send, now):
        for name in self.healthy(now):
            try:
                result = send(name, request)
            except Exception:
                self._report(name, False, now)
                continue
            self._report(name, True, now)
            return name, result
        raise AllProvidersDown("all providers down")
