# ruff: noqa
import copy

STAGES = ("none", "staging", "production", "archived")


class ModelRegistry:
    def __init__(self):
        self.models = {}   # name -> {"versions": [rec...], "holder": {stage: version}, "history": [versions]}

    def _model(self, name):
        if name not in self.models:
            raise KeyError(name)
        return self.models[name]

    def _rec(self, name, version):
        m = self._model(name)
        if not isinstance(version, int) or not (1 <= version <= len(m["versions"])):
            raise KeyError((name, version))
        return m["versions"][version - 1]

    def register(self, name, uri, metadata=None):
        if not uri:
            raise ValueError("uri required")
        m = self.models.setdefault(name, {"versions": [], "holder": {}, "history": []})
        version = len(m["versions"]) + 1
        m["versions"].append({"name": name, "version": version, "uri": uri, "stage": "none",
                              "metadata": copy.deepcopy(metadata) if metadata else {}})
        return version

    def get(self, name, version=None):
        m = self._model(name)
        if version is None:
            version = len(m["versions"])
        return copy.deepcopy(self._rec(name, version))

    def list_versions(self, name):
        return [copy.deepcopy(r) for r in self._model(name)["versions"]]

    def get_stage(self, name, stage):
        if stage not in ("staging", "production"):
            raise ValueError("stage")
        m = self._model(name)
        v = m["holder"].get(stage)
        return None if v is None else copy.deepcopy(m["versions"][v - 1])

    def promote(self, name, version, stage):
        if stage not in STAGES:
            raise ValueError("stage")
        rec = self._rec(name, version)
        m = self.models[name]
        old = rec["stage"]
        if old == stage:
            return
        if old in ("staging", "production") and m["holder"].get(old) == version:
            del m["holder"][old]
        if stage in ("staging", "production"):
            prev = m["holder"].get(stage)
            if prev is not None:
                m["versions"][prev - 1]["stage"] = "archived"
            m["holder"][stage] = version
            if stage == "production":
                m["history"].append(version)
        rec["stage"] = stage

    def rollback(self, name):
        m = self._model(name)
        hist = m["history"]
        cur = m["holder"].get("production")
        if cur is None or not hist or cur != hist[-1]:
            raise ValueError("nothing to roll back")
        if len(hist) < 2:
            raise ValueError("no previous production version")
        hist.pop()
        prev = hist[-1]
        m["versions"][cur - 1]["stage"] = "archived"
        m["versions"][prev - 1]["stage"] = "production"
        m["holder"]["production"] = prev
        return prev
