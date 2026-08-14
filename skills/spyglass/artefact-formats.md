# Artefact Formats

Reference for the spyglass skill. Read when writing artefacts in Phase 11, or when reading prior artefacts in Phase 1.

## Folder layout

```
<artefact-dir>/
├── .gitignore                       # contains "*" — makes this tree invisible to git
├── PLANS_INDEX.md
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
complexity_report      object    Phase 8 findings (if run)
refactor_signals       list      Fired signals — each {id, source_phase, evidence}
adopted_refactors      list      Selected at HIL-7 — each {recommendation, order, risk}
user_overrides         list      Entries of {hil, recommended, chosen, reason}
```

The per-phase **Receives** lines in `SKILL.md` cover most of this inline. The consolidated list matters most for the fields that cross many agent boundaries — `fast_path`, `prior_plans`, `current_sub_task`, and `user_overrides` — which are easy to drop precisely because no single phase owns them.
