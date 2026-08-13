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
