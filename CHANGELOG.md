# Changelog

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
