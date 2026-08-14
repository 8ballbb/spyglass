#!/usr/bin/env bash
# Reset the test fixture to a pristine state before a behavioural run.
#
# Spyglass writes design artefacts into the project it is run against, and a
# second run resumes from them instead of starting fresh. That is correct
# behaviour, and exactly wrong for testing — so clear them between runs.
#
# Also restores the fixture's Python files. The four planted conditions are the
# whole point of the fixture, and a run that "helpfully" tidied one would
# silently disable the check it exists to exercise.
#
# Usage:  tests/reset-fixture.sh
#
# WARNING: discards uncommitted changes under tests/fixtures/. That directory is
# fixed test data, not a workspace.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$REPO/tests/fixtures/sample-project"

echo "Resetting fixture: $FIXTURE"
echo

# 1. Artefacts written into the fixture, and into the repo root if resolution
#    ever walks past the fixture again.
for d in "$FIXTURE/.claude" "$REPO/.claude"; do
    if [ -e "$d" ]; then
        rm -rf "$d"
        echo "  removed  ${d#"$REPO"/}"
    fi
done

# 2. Artefacts from a no-project fallback run.
if [ -e "$HOME/.claude/spyglass" ]; then
    rm -rf "$HOME/.claude/spyglass"
    echo "  removed  ~/.claude/spyglass"
fi

# 3. Restore fixture sources, in case a run edited them.
if ! git -C "$REPO" diff --quiet -- tests/fixtures 2>/dev/null; then
    git -C "$REPO" checkout -- tests/fixtures
    echo "  restored tests/fixtures (a run had modified it)"
fi

find "$FIXTURE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo
echo "Planted conditions:"

fail=0
check() {  # name, result
    if [ "$2" = "ok" ]; then printf '  %-38s ok\n' "$1"
    else printf '  %-38s FAILED\n' "$1"; fail=1; fi
}

grep -q 'def normalise_date' "$FIXTURE/src/dataflow/timeutils.py" \
    && check "P1  reuse target normalise_date" ok \
    || check "P1  reuse target normalise_date" no

complexity=$(python3 - "$FIXTURE" <<'PY'
import ast, sys, pathlib
src = pathlib.Path(sys.argv[1], "src/dataflow/ingest.py").read_text()
fn = next(n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.FunctionDef) and n.name == "load_records")
c = 1
for n in ast.walk(fn):
    if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
        c += 1
    elif isinstance(n, ast.BoolOp):
        c += len(n.values) - 1
print(c)
PY
)
[ "$complexity" -gt 10 ] \
    && check "P2  load_records complexity ($complexity > 10)" ok \
    || check "P2  load_records complexity ($complexity, need > 10)" no

{ grep -q 'Args:' "$FIXTURE/src/dataflow/timeutils.py" \
  && grep -q 'Parameters' "$FIXTURE/src/dataflow/report.py"; } \
    && check "P3  docstring styles differ" ok \
    || check "P3  docstring styles differ" no

grep -q 'python-dateutil' "$FIXTURE/pyproject.toml" \
    && check "P4  python-dateutil declared" ok \
    || check "P4  python-dateutil declared" no

echo
if [ "$fail" -eq 0 ]; then
    echo "Fixture is clean. Run the test from:"
    echo "  $FIXTURE"
else
    echo "A planted condition is missing — the fixture cannot exercise every check."
    exit 1
fi
