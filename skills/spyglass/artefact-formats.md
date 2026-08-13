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
| csv-export-pipeline | CSV export for data pipeline | in-progress |
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
