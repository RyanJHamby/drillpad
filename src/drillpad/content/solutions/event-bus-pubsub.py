# ruff: noqa
import itertools
import threading


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs = {}                 # topic -> list of (token, handler)
        self._tokens = {}               # token -> topic
        self._ids = itertools.count(1)

    def subscribe(self, topic, handler):
        with self._lock:
            token = next(self._ids)
            self._subs.setdefault(topic, []).append((token, handler))
            self._tokens[token] = topic
            return token

    def unsubscribe(self, token):
        with self._lock:
            topic = self._tokens.pop(token, None)
            if topic is None:
                return False
            self._subs[topic] = [s for s in self._subs[topic] if s[0] != token]
            if not self._subs[topic]:
                del self._subs[topic]
            return True

    def publish(self, topic, event):
        with self._lock:
            targets = list(self._subs.get(topic, ()))
            if topic != "*":
                targets += list(self._subs.get("*", ()))
        delivered = 0
        for _, handler in targets:
            try:
                handler(event)
                delivered += 1
            except Exception:
                pass
        return delivered
