# ruff: noqa
class Node:
    __slots__ = ("name", "is_dir", "parent", "children", "content")

    def __init__(self, name, is_dir, parent=None):
        self.name, self.is_dir, self.parent = name, is_dir, parent
        self.children = {} if is_dir else None
        self.content = "" if not is_dir else None


class FileSystem:
    def __init__(self):
        self.root = Node("", True)
        self.root.parent = self.root          # ".." at root stays at root
        self.cwd = self.root

    def _walk(self, path):
        node = self.root if path.startswith("/") else self.cwd
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if not node.is_dir:
                return None
            if p == "..":
                node = node.parent
            elif p in node.children:
                node = node.children[p]
            else:
                return None
        return node

    def _split(self, path):
        """-> (parent dir Node | None, name) for creating/removing the last component."""
        parts = [p for p in path.split("/") if p not in ("", ".")]
        if not parts or parts[-1] == "..":
            return None, ""
        head = ("/" if path.startswith("/") else "") + "/".join(parts[:-1])
        parent = self._walk(head or ".")
        if parent is None or not parent.is_dir:
            return None, ""
        return parent, parts[-1]

    def mkdir(self, path):
        parent, name = self._split(path)
        if parent is None or name in parent.children:
            return False
        parent.children[name] = Node(name, True, parent)
        return True

    def touch(self, path):
        parent, name = self._split(path)
        if parent is None:
            return False
        existing = parent.children.get(name)
        if existing is not None:
            return not existing.is_dir
        parent.children[name] = Node(name, False, parent)
        return True

    def write_file(self, path, content):
        parent, name = self._split(path)
        if parent is None:
            return False
        existing = parent.children.get(name)
        if existing is not None and existing.is_dir:
            return False
        if existing is None:
            existing = parent.children[name] = Node(name, False, parent)
        existing.content = content
        return True

    def read_file(self, path):
        n = self._walk(path)
        return n.content if n is not None and not n.is_dir else None

    def ls(self, path="."):
        n = self._walk(path)
        if n is None:
            return None
        return sorted(n.children) if n.is_dir else [n.name]

    def cd(self, path):
        n = self._walk(path)
        if n is None or not n.is_dir:
            return False
        self.cwd = n
        return True

    def pwd(self):
        parts, n = [], self.cwd
        while n is not self.root:
            parts.append(n.name)
            n = n.parent
        return "/" + "/".join(reversed(parts))

    def rm(self, path):
        n = self._walk(path)
        if n is None or n.is_dir:
            return False
        del n.parent.children[n.name]
        return True

    def rmdir(self, path):
        n = self._walk(path)
        if n is None or not n.is_dir or n is self.root or n.children:
            return False
        a = self.cwd
        while True:                       # cannot remove cwd or an ancestor of cwd
            if a is n:
                return False
            if a is self.root:
                break
            a = a.parent
        del n.parent.children[n.name]
        return True
