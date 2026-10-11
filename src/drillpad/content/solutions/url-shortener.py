# ruff: noqa
import re

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _b62(n):
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return "".join(reversed(out)) or "0"


class UrlShortener:
    def __init__(self, base="http://sho.rt/"):
        self.base = base
        self.code_to_url = {}
        self.url_to_code = {}
        self.counter = 0

    def shorten(self, long_url, alias=None):
        if not long_url:
            raise ValueError("empty url")
        if alias is not None:
            if not re.fullmatch(r"[0-9a-zA-Z_-]{1,16}", alias):
                raise ValueError("bad alias")
            existing = self.code_to_url.get(alias)
            if existing is not None:
                if existing != long_url:
                    raise ValueError("alias taken")
                return self.base + alias
            self.code_to_url[alias] = long_url
            self.url_to_code.setdefault(long_url, alias)
            return self.base + alias
        code = self.url_to_code.get(long_url)
        if code is not None:
            return self.base + code
        while True:
            self.counter += 1
            code = _b62(self.counter)
            if code not in self.code_to_url:
                break
        self.code_to_url[code] = long_url
        self.url_to_code[long_url] = code
        return self.base + code

    def resolve(self, short_url):
        if not short_url.startswith(self.base):
            return None
        return self.code_to_url.get(short_url[len(self.base):])
