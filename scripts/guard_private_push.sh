#!/bin/sh
# pre-push guard: refuse to push this private working repository to a PUBLIC GitHub repository.
# The working repo holds personal practice material and firm-specific notes; publish through
# `python scripts/publish_check.py export` into a fresh repository instead.
# Fails closed: if visibility cannot be verified, the push is blocked unless DRILLPAD_ALLOW_UNVERIFIED_PUSH=1.
url="$2"
case "$url" in
  *github.com*)
    slug=$(printf '%s' "$url" | sed -E 's#^(git@github\.com:|https://([^@/]*@)?github\.com/|ssh://git@github\.com/)##; s#\.git$##')
    vis=$(gh repo view "$slug" --json visibility -q .visibility 2>/dev/null)
    case "$vis" in
      PRIVATE|INTERNAL) exit 0 ;;
      PUBLIC)
        echo "BLOCKED: $slug is PUBLIC. This working repository must stay private (see docs/MAINTAINING_THE_COURSE.md, 'Publishing a public copy')." >&2
        exit 1 ;;
      *)
        if [ "$DRILLPAD_ALLOW_UNVERIFIED_PUSH" = "1" ]; then
          echo "warning: could not verify visibility of $slug; pushing because DRILLPAD_ALLOW_UNVERIFIED_PUSH=1" >&2
          exit 0
        fi
        echo "BLOCKED: could not verify that $slug is private (is gh installed and logged in?). Set DRILLPAD_ALLOW_UNVERIFIED_PUSH=1 to override once." >&2
        exit 1 ;;
    esac ;;
esac
exit 0
