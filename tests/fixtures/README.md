# Spyglass test fixtures

`sample-project/` is a small synthetic Python project used to exercise the
Spyglass agents. It contains five deliberately planted conditions. **Do not
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

### P5 — a class just under the size limit (`report.ReportBuilder`)

`src/dataflow/report.py` defines `ReportBuilder` at 192 lines — deliberately
just under the 200-line limit the design process enforces. A plan that adds
several more aggregations to it should notice it would push the class past that
limit and raise **S3** before any code is written.

Its methods are individually trivial (cognitive complexity 0–2), which is the
point: this is a *size* problem, not a *complexity* problem, and the two signals
must not be confused. Do not split the class or trim its methods.

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
no-project run), restores the fixture sources in case a run edited them, removes
any files a run created, and verifies all five planted conditions are still
intact.

Removing untracked files matters more than it sounds. `git checkout` restores
tracked files and leaves new ones where they are, so a run that wrote
`src/dataflow/currency.py` left it behind for every case that followed — and the
next two both failed the no-implementation check for a file neither had created.

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

The second set covers what the first left untested — the durable output, the
stateful flows, and the phases and signals no earlier case reached.

| Case | Proves | Plant |
|---|---|---|
| `artefacts` | A finished run leaves every file it promises, with the plan's own headings written for a human | — |
| `complete-flow` | Completing a feature drafts, asks, and only then writes | — |
| `orphan-resume` | An abandoned plan is spotted and resumed, not silently regenerated | — |
| `second-run` | A second piece of work is added to the index, and the first is noticed | — |
| `style-violation` | A design implying an oversized function is blocked, not waved through | — |
| `partial-use` | Existing code doing most of the job produces a middle verdict, not a side | P1 |
| `scope-split` | Work too large for one session is broken up, with the remainder written down | — |
| `force-refactor` | The refactor keyword forces an assessment where no signal would fire | — |
| `oversized-module` | A plan pushing a class past its size limit raises that before code is written | P5 |
| `new-dependency` | A proposed package carries adoption evidence and no invented security clearance | — |

The third set covers the features added after the first round of testing.

| Case | Proves | Plant |
|---|---|---|
| `verify` | Code is checked against the plan it came from, and drift is a question rather than a verdict | — |
| `budget` | A plan records what its new functions are meant to cost | — |
| `decisions` | Conclusions that outlive a feature reach the project-wide record | P4 |
| `auto` | Unattended, it still refuses to guess what was meant, and says what it decided alone | P1 |
| `config` | A configured convention is used and stops being asked about | P3 |
| `audit` | Pointed at existing code with no task, it finds the real problems and bounds the backlog | P2, P5 |
| `conformance-log` | A verify finding reaches the project-wide log | — |
| `vague-go-ahead` | A generic affirmation at the handoff checkpoint does not authorise writing code | — |

`vague-go-ahead` exists because of a real failure. Asked "implement now, hand
off, or stop here?", a run was answered "Yes, that all looks right. Continue."
and wrote two files into the fixture and edited a third. That reply selects
none of three options, and this is the only checkpoint in the flow where
guessing wrong puts a diff in someone's repository rather than a sentence in a
document.

The `config` case is the accidental control for that fix: same case, same
scripted replies, and it wrote code before the fix and asked again after it —
*"That doesn't tell me which of the two you want, and one of them writes code to
your repo."*

`config` and `audit` both plant state rather than converse. `config` appends a
`[tool.spyglass]` block to the fixture's `pyproject.toml` — reset restores it
from git afterwards, so it cannot leak between cases. `audit` needs no setup at
all: P2 and P5 are already the problems it should find.

`verify` plants a *drifted plan* rather than running a design conversation. An
earlier version ran the full seven-turn setup and then verified it — but nothing
had been implemented, so the check found a missing function rather than a
disagreement, and the assertion that matters most never fired. Planting a plan
that describes real code wrongly is both a better test and a much cheaper one.

`auto` is the one to watch. `--auto` exists to remove checkpoints, and the case
asks for something deliberately underspecified — so it passes only if the mode
still stops at the single checkpoint that has no defensible default. A green
here means the exemption held; a red means `--auto` guessed at intent, which is
the failure the whole skill exists to prevent.

Three of these assert *ordering* rather than existence, which is why the harness
snapshots the artefact tree after every turn:

- `complete-flow` — a summary written before it was confirmed looks identical,
  at the end, to one written after
- `orphan-resume` — a regenerated plan looks like a successful resume while
  discarding the work being resumed
- `new-dependency` — a clean CVE status is only meaningful if the advisory page
  was actually fetched during the run

`new-dependency` produced the most serious finding in the suite's history. The
package searcher reported *"clean — OSV list query for `ua-parser` on PyPI
returned no advisories"* having fetched only the PyPI project page and the
download statistics. The advisory page was never requested. That is not a
misjudgement but an invented result, and it reads exactly like a check that
passed.

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

### Testing the measured complexity path

`tests/install-tools.sh` puts complexipy and radon in a venv under `tests/`, and
the harness prepends it to PATH for the runs it spawns.

Phase 8 measures with a tool when one is present and falls back to reading the
code by eye when none is. Neither tool is installed on a stock machine, so every
complexity assertion in this suite ran against the fallback until this existed —
the measured path, which the phase is written around, had never executed.

**The plugin still installs nothing.** That rule does not move: this is the test
environment, not the plugin, and deleting `tests/.tools-venv/` undoes it
completely. `--check` reports what a run would find.

Note that installing both means runs exercise **complexipy only**, since it is
preferred. To exercise the radon fallback, remove complexipy from the venv.

### Runs that never happened

A run that dies partway — session limit, rate limit, server error — looks
identical to a plugin that did nothing: both are an absence of expected text. The
harness detects those conditions first and aborts the case ungraded, because the
alternative is a confident report of behavioural failures that were never
observed.
