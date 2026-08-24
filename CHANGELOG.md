# Changelog

## 0.3.0 — 2026-08-24

### Fixed

- **A vague answer at the final checkpoint no longer authorises writing code.**
  Asked "implement now, hand off, or stop here?" and answered "yes, that all
  looks right, continue", Spyglass wrote two files and edited a third. A generic
  affirmation selects none of three options, and this is the only checkpoint
  where guessing wrong puts a diff in your repository rather than a sentence in
  a document. It now asks again, and defaults to stopping.

### Added

- **`--verify <slug>`** — compares implemented code against the plan it came
  from. Signatures are parsed rather than read by eye, complexity is measured
  against the budget the plan set, and `mypy` is used where installed to check
  the types a contract stated actually hold. Drift is reported as a question,
  not a verdict: implementation legitimately discovers what design could not, so
  updating the plan is a valid answer.
- **`--audit <path>`** — assess code that already exists, with no task. Returns
  a prioritised backlog ordered by what each finding costs to live with rather
  than by severity label, capped at fifteen. Everything else here needs a task
  before it is any use.
- **`--auto`** — run to completion, taking the default at every checkpoint
  except two: a genuinely ambiguous request, and a hard style violation. Every
  decision taken is reported at the end and recorded as auto-taken rather than
  user-confirmed.
- **Complexity budgets.** Plans now record what each new function is meant to
  cost, so `--verify` can check what it does. A threshold agreed before the code
  exists is something no linter can offer.
- **`[tool.spyglass]` configuration** in `pyproject.toml`, or `.spyglass.toml`.
  Settles the docstring convention, complexity budget, size limits, and paths to
  skip. Never written by Spyglass; what you say in a session always wins.
- **`decisions.md`** — project-level memory. Conclusions that outlive a feature
  are recorded once instead of re-derived by four agents every time.
- **`conformance-log.md`** — one row per verify finding. The same drift three
  times is a fact about how a project designs, and the design phase now reads it
  back. Two is a coincidence and stays silent.

## 0.2.0 — 2026-08-20

Behavioural testing found bugs that structural validation could not. Everything
below was observed in a real run against a real project, not reasoned about.

### Fixed

- **A clarifying question now offers doing nothing.** Asked to "clean up dates"
  in a codebase that already had a date normaliser, every option Spyglass
  offered built something new. Where existing code plausibly covers the job,
  "use it as it is and write nothing" is now an option, listed first.
- **Internal signal identifiers no longer reach you.** Runs reported things like
  `S1 fired — the function being touched is dense`. Those identifiers are
  bookkeeping; you now get the finding instead.
- **A dependency's security status can no longer be invented.** The package
  search reported `clean — OSV list query returned no advisories` for a package
  whose advisory page it had never requested. A clean status now requires the
  check to have actually run, and the URL is reported alongside it. An unchecked
  package presented as vetted is worse than no recommendation, because it clears
  a gate that was never opened.
- **Design notes no longer carry internal stage names.** Plans used `Level 1` as
  a heading, which surfaced whenever a plan was shown back to you.
- **`--no-refactor` no longer suppresses the measurement.** It suppresses the
  refactor assessment. Knowing a change lands in a dense function is useful even
  when you have already decided not to restructure it.
- **The package searcher no longer tries to fetch local file paths.** It has no
  filesystem access, and one run guessed a public GitHub URL for a local file
  when a fetch failed. Its input arrives inline, and it is now told so.

### Added

- **`complexipy` support, preferred over `radon`.** Cyclomatic complexity is
  blind to nesting, which is what actually makes a function hard to change. On
  one real function radon reported grade C (14, four over its threshold) while
  complexipy reported 28 against a threshold of 15. Where complexipy is present,
  its `--suggest-refactors` line ranges and estimated reductions are passed to
  the refactor assessment as measured evidence rather than estimated by eye.
- Both tools remain **optional and never prompted for**. If neither is
  installed, Spyglass assesses complexity by reading the code and says that the
  figures are estimates.

## 0.1.0

Initial release.
