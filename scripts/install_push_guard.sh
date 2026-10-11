#!/bin/sh
# Install the private-push guard as .git/hooks/pre-push in a repository (default: this one).
repo="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
src="$(cd "$(dirname "$0")" && pwd)/guard_private_push.sh"
dest="$repo/.git/hooks/pre-push"
if [ -e "$dest" ] && ! cmp -s "$src" "$dest"; then
  echo "refusing to overwrite an existing different $dest" >&2
  exit 1
fi
cp "$src" "$dest" && chmod +x "$dest" && echo "installed $dest"
