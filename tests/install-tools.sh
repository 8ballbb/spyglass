#!/usr/bin/env bash
# Put the optional complexity tools where a behavioural run can find them.
#
# WHY THIS EXISTS
#
# Phase 8 measures with radon or complexipy when they are present, and --verify
# type-checks with mypy when it is, and falls
# back to reading the code by eye when they are not. Neither is installed on a
# stock machine, so every complexity assertion in this suite has so far
# exercised the fallback. The measured path — the one the phase is actually
# written around — had never run.
#
# The plugin must never install anything; that rule is not negotiable and this
# script does not change it. It installs into a venv under tests/, which the
# harness prepends to PATH for the runs it spawns. Nothing global is touched,
# and deleting the directory undoes it completely.
#
# Usage:  tests/install-tools.sh          set it up
#         tests/install-tools.sh --check  report what a run would find
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/tests/.tools-venv"

if [ "${1:-}" = "--check" ]; then
    if [ -x "$VENV/bin/radon" ] && [ -x "$VENV/bin/complexipy" ] && [ -x "$VENV/bin/mypy" ]; then
        echo "measured path available:"
        "$VENV/bin/radon" --version | sed 's/^/  /'
        "$VENV/bin/complexipy" --version 2>/dev/null | sed 's/^/  complexipy /' || true
        "$VENV/bin/mypy" --version | sed 's/^/  /'
        exit 0
    fi
    echo "not installed — runs will exercise the by-eye fallback only" >&2
    exit 1
fi

python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet radon complexipy mypy
echo "Installed into tests/.tools-venv:"
"$VENV/bin/radon" --version | sed 's/^/  /'
echo "  complexipy $("$VENV/bin/complexipy" --version 2>/dev/null || echo installed)"
echo
echo "The harness adds this to PATH for the runs it spawns. Nothing global changed."
