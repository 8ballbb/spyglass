#!/usr/bin/env bash
# Copy the working tree into the installed plugin cache.
#
# WHY THIS EXISTS
#
# `claude plugin install` takes a snapshot. It does not symlink the source, and
# nothing re-reads this repo afterwards — so editing SKILL.md here changes
# nothing about what a behavioural run exercises. The run still passes, still
# prints green, and is testing the last published version.
#
# That was not hypothetical. Four cases were graded against a cache with no
# HIL-1b in it at all, including the case written specifically to test HIL-1b.
# It passed, because the base model happened to ask a clarifying question on its
# own. A green run against stale code is worse than a red one: it certifies
# behaviour that the thing being tested does not have.
#
# So: sync before every run, and have the harness refuse to start if the cache
# and the working tree disagree.
#
# Usage:  tests/sync-plugin.sh [--check]
#           (no args)  copy the working tree into the cache
#           --check    report drift and exit 1, copy nothing

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_ROOT="$HOME/.claude/plugins/cache/spyglass/spyglass"

if [ ! -d "$CACHE_ROOT" ]; then
    echo "Spyglass is not installed — nothing to sync." >&2
    echo "Install it first; a behavioural run needs the real plugin loader." >&2
    exit 1
fi

# Installed versions are directories named for the version. Take the newest, so
# a version bump does not silently keep testing the old one.
CACHE="$CACHE_ROOT/$(ls -1 "$CACHE_ROOT" | sort -V | tail -1)"

# Only what the plugin loader actually reads. Tests, docs and assets are not
# part of the runtime and copying them just makes the diff noisy.
PARTS=(skills agents .claude-plugin)

drift() {
    local found=1
    for p in "${PARTS[@]}"; do
        if ! diff -rq "$CACHE/$p" "$REPO/$p" >/dev/null 2>&1; then
            diff -rq "$CACHE/$p" "$REPO/$p" 2>&1 | sed 's/^/  /'
            found=0
        fi
    done
    return $found
}

if [ "${1:-}" = "--check" ]; then
    if drift; then
        echo
        echo "Installed plugin differs from the working tree — run tests/sync-plugin.sh" >&2
        exit 1
    fi
    echo "Installed plugin matches the working tree ($(basename "$CACHE"))."
    exit 0
fi

for p in "${PARTS[@]}"; do
    rm -rf "${CACHE:?}/$p"
    cp -R "$REPO/$p" "$CACHE/$p"
done

echo "Synced working tree → $(basename "$CACHE")"
for p in "${PARTS[@]}"; do
    printf '  %s\n' "$p"
done
