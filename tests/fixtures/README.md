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
tests/run-behavioural.py --case X --repeat 5   # pass rate, not a verdict
```

`--repeat` exists because intermittent behaviour is a real failure class and a
single run cannot see it. `no-refactor` passed, failed, passed, failed against
identical input — the spec named the phase that `--no-refactor` suppresses and
left the neighbouring phase's fate to inference, so the model inferred it
differently each time. `3/5` and `0/5` are different bugs: an ambiguous
instruction, versus behaviour that is not there at all.

Runs that die before they start are reported separately and excluded from the
rate. A run with no opinion about the plugin should not contribute one.

Every assertion is deterministic — string and filesystem checks, no LLM judge. A
grader that needs a model to decide whether it passed is a grader that can
disagree with itself between runs.

Runs use `--permission-mode bypassPermissions` because this fixture is disposable
test data, reset before every run. `acceptEdits` is not enough: the run stops to
ask before creating its notes directory, and a harness that needs a human to
unblock it is not a harness.

Each run spawns real agents and costs real tokens. Nothing runs without being
asked for.

### Cases

| Case | Proves | Plant |
|---|---|---|
| `stops` | A bare request stops at the first checkpoint, in plain language, without writing code | — |
| `reuse` | The reuse phase actually runs, finds the planted duplicate, and gives the declared dependency a reasoned verdict | P1, P4 |
| `dont-write-it` | When existing code already does the job, it recommends using it instead of designing a duplicate | P1 |
| `modify` | Changing existing code skips the reuse hunt, but still measures complexity and raises refactoring unprompted | P2 |
| `no-refactor` | The suppression keyword beats a signal that really fired, without suppressing the measurement | P2 |
| `force-tests` | The test keyword pulls test planning onto a light path that skips it by default | P4 |
| `already-done` | Asked for something the code already does, it says so and stops | P2 |
| `patterns` | A cross-cutting request takes the full path and reports that the target directory's conventions disagree | P3 |
| `holds-out` | Fed non-answers to a question that decides the design, it keeps asking rather than guessing | — |
| `ambiguous` | An open-ended request is clarified before anything is designed, and "use what exists" is on the menu | P1 |
| `no-project` | Outside a Python project, notes go to `~/.claude/spyglass` and it says so | — |

Four of these — `dont-write-it`, `already-done`, `ambiguous`, `holds-out` — test
the same thing from different angles: **not building something**. That is
deliberate. Recommending a new function where `normalise_date` already exists is
the reimplementation failure this plugin exists to prevent, and a design process
that cannot say "no work needed" will always find work.

### A case can be made obsolete by an improvement

`dont-write-it` used to require all four investigation agents. Once the
clarification checkpoint existed, they stopped running: it recognises
`normalise_date` at the second turn and offers to stop, reaching the same answer
without spending them. The check failed a run that was cheaper and just as right.

When a case fails, the first question is not "what broke" but "is this still the
right thing to ask for". Three of the failures in this suite's history were the
plugin being right and the case being wrong.

Run `tests/selftest-harness.py` first — it costs nothing and catches harness bugs
that would otherwise be discovered minutes and several agents into a live run.

### Testing the thing you actually changed

`tests/sync-plugin.sh` copies the working tree into the installed plugin cache,
and every case runs it first.

`claude plugin install` takes a snapshot; it does not track this repo. Without
the sync, editing `SKILL.md` changes nothing about what a run exercises — the run
still prints green, against the last published version. That is not
hypothetical: four cases were graded against a cache with no HIL-1b in it,
including the case written to test HIL-1b. It passed, because the base model
asked a clarifying question on its own.

`tests/sync-plugin.sh --check` reports drift without changing anything.

### Runs that never happened

A run that dies partway — session limit, rate limit, server error — looks
identical to a plugin that did nothing: both are an absence of expected text. The
harness detects those conditions first and aborts the case ungraded, because the
alternative is a confident report of behavioural failures that were never
observed.
