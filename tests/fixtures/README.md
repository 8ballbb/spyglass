# Spyglass test fixtures

`sample-project/` is a small synthetic Python project used to exercise the
Spyglass agents. It contains four deliberately planted conditions. **Do not
"fix" any of them** — each one is the target signal for a specific agent's
tests, and removing it will break those tests.

## Planted conditions

### P1 — near-duplicate function (`timeutils.normalise_date`)

`src/dataflow/timeutils.py` defines `normalise_date`, a function that is a
near-duplicate of a plausible planned/expected function. This gives
`codebase-searcher` an `exact`/`partial` match to find when searching for
similar functionality, and lets `investigation-synthesiser` raise finding
**S2** (near-duplicate implementation) from that search result.

### P2 — high cyclomatic complexity (`ingest.load_records`)

`src/dataflow/ingest.py` defines `load_records` with deliberately convoluted
nested conditionals, `try`/`except` handling, and compound boolean
expressions. Its cyclomatic complexity is above 10 (graded C or worse), so
`complexity-assessor` raises finding **S1** (excessive complexity) against it.
Do not simplify, flatten, or extract helpers from this function — the
complexity is the point.

### P3 — inconsistent docstring style (`timeutils.py` vs `report.py`)

`src/dataflow/timeutils.py` uses Google-style docstrings (`Args:`,
`Returns:`, `Raises:`), while `src/dataflow/report.py` uses NumPy-style
docstrings (`Parameters`/`Returns` with underlined sections). This
inconsistency is intentional so that `pattern-analyzer` reports the
docstring convention as `inconsistent` across the codebase and raises
finding **S4**. Do not harmonise the two styles.

### P4 — real dependency and test config (`pyproject.toml`)

`pyproject.toml` declares a real dependency (`python-dateutil>=2.8`) and a
pytest configuration (`[tool.pytest.ini_options]` with `testpaths`). This
gives `deps-searcher` and `test-planner` real configuration to read and
report on rather than an empty project.

## Warning

These conditions are the fixture's entire purpose. Refactoring
`load_records`, unifying the docstring styles, deduplicating
`normalise_date`, or changing `pyproject.toml`'s dependencies will cause the
corresponding Spyglass agent tests to fail or produce false negatives.

## Resetting between runs

Run `tests/reset-fixture.sh` before every behavioural test.

Spyglass writes design artefacts into the project it runs against, and a second
run **resumes from them** rather than starting fresh — correct behaviour, and
exactly wrong for testing. The script clears artefacts from all three locations
a run can write to (the fixture, the repo root, and `~/.claude/spyglass` from a
no-project run), restores the fixture sources in case a run edited them, and
verifies all four planted conditions are still intact.

It exits non-zero if a plant has gone missing, so a fixture that can no longer
exercise every check fails loudly instead of passing a weakened test.

## Automated behavioural tests

`tests/run-behavioural.py` drives the plugin headlessly against this fixture and
grades both the transcript and the filesystem side effects.

```
tests/run-behavioural.py --list      # show cases, spend nothing
tests/run-behavioural.py --dry-run   # show the commands, spend nothing
tests/run-behavioural.py             # run the default case
tests/run-behavioural.py --case all  # run everything
```

Every assertion is deterministic — string and filesystem checks, no LLM judge. A
grader that needs a model to decide whether it passed is a grader that can
disagree with itself between runs.

Runs use `--permission-mode bypassPermissions` because this fixture is disposable
test data, reset before every run. `acceptEdits` is not enough: the run stops to
ask before creating its notes directory, and a harness that needs a human to
unblock it is not a harness.

Each run spawns real agents and costs real tokens. Nothing runs without being
asked for.
