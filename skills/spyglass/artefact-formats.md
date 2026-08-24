# Artefact Formats

Reference for the spyglass skill. Read when writing artefacts in Phase 11, or when reading prior artefacts in Phase 1.

## Folder layout

```
<artefact-dir>/
├── .gitignore                       # contains "*" — makes this tree invisible to git
├── PLANS_INDEX.md
├── decisions.md                     # project-wide; survives individual features
├── conformance-log.md               # one row per --verify finding; the only file that compounds
├── audits/
│   └── <yyyy-mm-dd>.md              # --audit reports
└── <feature-slug>/
    ├── INDEX.md
    ├── pseudocode.md
    ├── pseudocode.prev.md           # transient; exists only during an unresolved HIL-5b
    ├── test-plan.md                 # only if Phase 10 ran
    ├── future-tasks.md              # sub-tasks and/or deferred refactors
    ├── session-context.md
    └── completed-summary.md         # only after --complete
```

## Status vocabularies

Declared so they do not drift between sessions.

`PLANS_INDEX.md` → `Status`:

| Value | Meaning |
|---|---|
| `planning` | Design artefacts exist; implementation has not started |
| `in-progress` | Implementation started; more sessions needed |
| `session-done` | This session's work finished; feature not yet confirmed complete |
| `complete` | User invoked `--complete` |

`INDEX.md` → `Status`:

| Value | Meaning |
|---|---|
| `current` | Exists and is up to date |
| `superseded` | Replaced by newer content elsewhere in the folder |
| `pending` | Planned but not yet written |
| `not-run` | Optional phase did not run, so the file does not exist |

## `PLANS_INDEX.md`

```markdown
# Plans Index

| Folder | Description | Status |
|--------|-------------|--------|
| csv-export-data-pipeline | CSV export for data pipeline | in-progress |
| auth-refactor | JWT auth middleware replacement | complete |
```

## `<feature>/INDEX.md`

Optional files appear as `not-run` when skipped:

```markdown
# <Feature Name> — Task Index

| File | Contents | Status |
|------|----------|--------|
| pseudocode.md | Three-level design plan, 1 preliminary refactor | current |
| session-context.md | Schema notes, override decisions, declined refactors | current |
| future-tasks.md | 2 deferred refactors | current |
| test-plan.md | — | not-run |
| completed-summary.md | — | pending |
```

## `decisions.md`

Project-wide, not per-feature. Read in **Phase 1**, appended in **Phase 11**.

Everything else here is scoped to one feature, so each new feature re-derives conclusions the last one already reached. Across a single day of testing, `python-dateutil is declared but not installed` was rediscovered four times and dateutil was independently reasoned about and rejected twice. Four agents ran each time to arrive somewhere the project already knew.

```markdown
# Decisions

| Date | Decision | Because | From |
|------|----------|---------|------|
| 2026-08-14 | Not adopting `python-dateutil` | Declared in pyproject.toml but not installed; the inputs are epoch seconds, which it does not parse | convert-timestamp-iso8601 |
| 2026-08-19 | New aggregations go in their own module, not `ReportBuilder` | The class is already near the 200-line limit | aggregations-reportbuilder |
```

**Record only decisions with reasons that outlive their feature.** "We chose the name `to_iso8601`" is feature-scoped and belongs in `session-context.md`. "This project does not take on new date-parsing dependencies" is not.

**Consult it in Phase 5, before dispatching the searchers.** A prior rejection is a strong prior, not a rule: cite it, say when it was made, and re-check anything that turns on a fact that may have changed — an uninstalled package may since have been installed. Never treat an old decision as closing a question the user has just reopened by asking.

**Never rewrite or delete an entry.** Superseding one means adding a new row that says so. The value here is the reasoning trail, and a trail that gets tidied is just the current state with extra steps.

## `conformance-log.md`

One row per `--verify` finding, appended after HIL-11. Project-wide.

```markdown
# Conformance log

| Date | Feature | Symbol | Finding | Resolved by |
|------|---------|--------|---------|-------------|
| 2026-08-24 | date-normalisation | normalise_date | signature-drift: planned `tz: str`, built `assume_utc: bool` | updated the plan |
| 2026-08-24 | csv-export | write_rows | missing | left flagged |
```

**This is the only artefact that gets more useful the more there is of it.** Everything else is read within the feature that wrote it and then rarely again. A single drift is noise; the same drift four times is a fact about how this project designs.

**Read it in Phase 4b, and act only on repetition.** Where the same finding type has occurred **three or more times**, say so once while designing the thing likely to repeat it:

> Three of the last five plans here understated their parameters — an `errors` or `encoding` argument turned up during implementation. Worth deciding now whether this one needs it.

**Three, not two.** Two is a coincidence, and a design pass that lectures on the strength of two data points is worse than one that says nothing. Never present a pattern as a rule: it describes what has happened, not what must.

**Never rewrite rows.** As with `decisions.md`, the value is the trail.

## `<feature>/pseudocode.md`

The design itself, and the only artefact a human reads closely. Use exactly these headings:

```markdown
# <feature-slug>

## Module design
## Contracts
## Signatures
```

**Never `Level 1`, `Level 2` or `Level 3`.** Those name the stages of *writing* the plan, not sections of it. The distinction is not pedantic: this file is shown back at checkpoints, so a heading inside it becomes a heading on the user's screen, and a run once presented `## Level 1 — Module design` to someone who had never heard the term. The format was unspecified, so the model borrowed the stage names it had been given.

Where a refactor is adopted with `order: before-current-task`, it goes in a **Preliminary refactors** section at the top, above *Module design* — implementation performs those first, so new code lands on sound structure.

## Single-session success path

Write `session-context.md`; set `PLANS_INDEX.md` to `session-done`. `future-tasks.md` only if deferred refactors exist. `INDEX.md` marks present files `current` and absent optional files `not-run`. Status becomes `complete` only via `--complete`.

## `session-context.md`

Written by the main Claude instance after HIL-9 confirms content:

- Key decisions and reasons, especially HIL overrides
- Technical context future sessions need — schemas, constraints, interface contracts
- Refactor recommendations declined, with motivating signal
- Remaining sub-tasks and order (multi-session only)

## `user_overrides` entry format

```
hil:           HIL number where the override occurred
recommended:   What the agent recommended
chosen:        What the user chose instead
reason:        User's stated reason, or "no reason given"
```

## Feature slug consistency

At HIL-1, always show the generated slug alongside existing ones, so a re-phrased task can be pointed at the folder it belongs to. Consistency comes from explicit confirmation, not algorithmic matching.

## Context Handoff Contract

Not a literal data structure — what must appear explicitly in each agent's prompt so context is not silently dropped across agent boundaries. The main Claude instance carries it forward.

```
task_description       string    Original user task
artefact_dir           path      Resolved in Phase 1
feature_slug           string    Confirmed at HIL-1
fast_path              enum      none | fast-path-modify | fast-path-add
module_design          object    Phase 4a Level 1 (confirmed at HIL-2)
patterns               object    Codebase conventions confirmed at HIL-2
pseudocode_doc_path    path      <artefact_dir>/<slug>/pseudocode.md
scope                  enum      single-session | multi-session (confirmed at HIL-4)
current_sub_task       string    What we are implementing this session
prior_plans            list      Relevant artefacts confirmed at HIL-1
library_recommendation object    Phase 6 synthesis (approved at HIL-5)
style_violations       list      Phase 7 findings (resolved at HIL-6)
complexity_report      object    Phase 8 findings (if run) — includes the tool used
                                 and, where complexipy ran, its refactor plans
refactor_signals       list      Fired signals — each {id, source_phase, evidence}
adopted_refactors      list      Selected at HIL-7 — each {recommendation, order, risk}
user_overrides         list      Entries of {hil, recommended, chosen, reason}
```

The per-phase **Receives** lines in `SKILL.md` cover most of this inline. The consolidated list matters most for the fields that cross many agent boundaries — `fast_path`, `prior_plans`, `current_sub_task`, and `user_overrides` — which are easy to drop precisely because no single phase owns them.
