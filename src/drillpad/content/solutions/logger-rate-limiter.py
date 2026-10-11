# ruff: noqa
class Logger:
    WINDOW = 10

    def __init__(self):
        self.last = {}

    def should_print(self, timestamp, message):
        prev = self.last.get(message)
        if prev is None or timestamp >= prev + self.WINDOW:
            self.last[message] = timestamp
            return True
        return False
