# ruff: noqa
import json
import re

_SPLIT = re.compile(r"\r\n|\r|\n")


class SSEParser:
    def __init__(self):
        self.pending = ""
        self.etype = ""
        self.data = []
        self.last_id = None
        self.done = False

    def _line(self, line, out):
        if line == "":
            if self.data:
                data = "\n".join(self.data)
                if data == "[DONE]":
                    self.done = True
                else:
                    out.append({"event": self.etype or "message", "data": data, "id": self.last_id})
            self.etype, self.data = "", []
            return
        if line.startswith(":"):
            return
        if ":" in line:
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field, value = line, ""
        if field == "data":
            self.data.append(value)
        elif field == "event":
            self.etype = value
        elif field == "id":
            self.last_id = value

    def feed(self, chunk):
        if self.done:
            return []
        buf = self.pending + chunk
        hold = ""
        if buf.endswith("\r"):
            hold, buf = "\r", buf[:-1]
        parts = _SPLIT.split(buf)
        self.pending = parts.pop() + hold
        out = []
        for line in parts:
            self._line(line, out)
            if self.done:
                self.pending = ""
                break
        return out

    def close(self):
        self.pending = ""
        self.etype, self.data = "", []
        return []


def assemble(chunks):
    p = SSEParser()
    text = []
    for c in chunks:
        for ev in p.feed(c):
            text.append(json.loads(ev["data"]).get("delta", ""))
    return "".join(text)
