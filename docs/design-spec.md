# Spyglass — Plugin Design Spec

**Date:** 2026-08-12
**Status:** Draft — pending user review
**Revision:** 7 (named; packaged as a distributable plugin)

---

## The Name

**Spyglass.** Named for the instrument you raise before you cross unfamiliar ground. It doesn't move you an inch — it just means you know what's out there before you commit.

This line belongs in the README beneath the project image, and in the plugin description where it fits.

The `py` sits natively inside "spy", so the name is a real word rather than a respelling — nothing to explain, nothing to be told is a typo, and it searches cleanly.

---

## Overview

A Claude Code plugin providing a skill that enforces disciplined Python development by running structured design analysis before any implementation. It prevents common failure modes: reimplementing existing functionality, ignoring codebase conventions, writing oversized functions and classes, never considering refactoring, and blindly starting tasks that are too large for one session.

**Distributed as a plugin** anyone can install. It must therefore work in any repository, under any team's conventions, with zero configuration and no surprising side effects.

**Invocation:**
- `/spyglass:spyglass <task description>` — standard run
- `/spyglass:spyglass --tests <task description>` — force test planning
- `/spyglass:spyglass --refactor <task description>` — force refactor assessment even when no signal fires
- `/spyglass:spyglass --no-refactor <task description>` — suppress refactor assessment even when signals fire
- `/spyglass:spyglass --complete <feature-slug>` — mark a feature complete and write summary

These are keywords recognised in the invocation text, not CLI flags.

The `plugin:skill` form is required — see Invocation below. The skill is also model-invoked, so in practice it engages without being typed.

Refactor assessment is **signal-driven by default** — the skill detects when refactoring is warranted and runs the assessment on its own. The two keywords override that judgment in either direction; neither is needed for normal use.

**Scope:** Python projects only.

**Terminal state:** The skill produces design artefacts and stops. It does not implement. Phase 12 presents the artefacts and asks how to proceed — implementation is always a separate, explicitly-chosen step.

### Design constraints imposed by being a plugin

Every one of these exists because a stranger will install this into a repository the author has never seen.

| Constraint | Consequence in this spec |
|---|---|
| Never dirty a user's working tree unasked | Artefacts go to `.claude/spyglass/`, self-ignored from git |
| Never edit a user's tracked config files | The root `.gitignore` is never modified — see Git invisibility below |
| No hard dependency on other plugins | Phase 12's handoff to `superpowers:writing-plans` is offered only if superpowers is installed |
| No hard dependency on external tools | radon improves Phase 8 but is never required and never prompted for |
| Must work outside a project | Phase 1 has a defined no-project fallback |
| Agent names are already namespaced | Agents are `pattern-analyzer`, not `python-pattern-analyzer` — the plugin prefix is automatic |

### Cost expectations

Derived from each path's run list, counting one agent per agent-backed phase. Phases 1, 2a, 4a, 4b, 11, and 12 run on the main instance and spawn nothing.

| Path | Agents spawned | Which |
|---|---|---|
| `fast-path-modify` | 3–4 | scope-assessor, style-checker, complexity-assessor, + refactor-assessor if a signal fires |
| `fast-path-add` | 5–6 | scope-assessor, codebase-searcher, stdlib-searcher, synthesiser, style-checker, + refactor-assessor if a signal fires |
| Standard, no conditionals, no signals | 7 | scope-assessor, 4 searchers, synthesiser, style-checker |
| Standard with pattern analysis and complexity assessment | 9 | the above + pattern-analyzer, complexity-assessor |
| Everything including refactor and test planning | 11 | all |

---

## Plugin Packaging

### Repository structure

As built:

```
spyglass/
├── .claude-plugin/
│   ├── plugin.json              # plugin manifest
│   └── marketplace.json         # self-hosted marketplace manifest
├── skills/
│   └── spyglass/
│       ├── SKILL.md             # the workflow
│       ├── python-standards.md  # distilled Google Style Guide + PEP 8
│       └── artefact-formats.md  # folder layout, status vocabularies, templates
├── agents/
│   ├── pattern-analyzer.md
│   ├── scope-assessor.md
│   ├── codebase-searcher.md
│   ├── stdlib-searcher.md
│   ├── deps-searcher.md
│   ├── package-searcher.md
│   ├── investigation-synthesiser.md
│   ├── style-checker.md
│   ├── complexity-assessor.md
│   ├── refactor-assessor.md
│   └── test-planner.md
├── docs/
│   ├── design-spec.md           # this file
│   └── implementation-plan.md
├── tests/
│   ├── validate-agents.py       # frontmatter + reference validator, stdlib only
│   └── fixtures/
│       ├── README.md
│       └── sample-project/      # planted conditions for agent verification
├── assets/
│   └── spyglass.png             # project image, referenced by README
├── .gitignore                   # standard Python/macOS ignores
├── README.md
└── LICENSE                      # MIT
```

### `.claude-plugin/plugin.json`

```json
{
  "name": "spyglass",
  "description": "Design-first Python development: pseudo-code planning, reuse investigation, style enforcement, and signal-driven refactor detection before any code is written",
  "version": "0.1.0",
  "author": { "name": "<author>", "email": "<email>" },
  "homepage": "https://github.com/<user>/spyglass",
  "repository": "https://github.com/<user>/spyglass",
  "license": "MIT",
  "keywords": ["python", "design", "planning", "refactoring", "code-quality", "pep8"]
}
```

### `.claude-plugin/marketplace.json`

```json
{
  "$schema": "https://www.schemastore.org/claude-code-marketplace.json",
  "name": "spyglass",
  "description": "Design-first Python development for Claude Code.",
  "owner": { "name": "<author>", "url": "https://github.com/<user>" },
  "plugins": [
    {
      "name": "spyglass",
      "description": "Pseudo-code planning, reuse investigation, and style enforcement before any Python is written.",
      "source": "./",
      "category": "productivity",
      "tags": ["python", "design", "planning", "refactoring", "code-quality"]
    }
  ]
}
```

### Installation

```
/plugin marketplace add <user>/spyglass
/plugin install spyglass@spyglass
```

### Invocation — no command wrapper

**There is no `commands/` directory, deliberately.** An earlier revision of this spec called for a thin `commands/spyglass.md` wrapper so users could type `/spyglass` instead of `/spyglass:spyglass`. That was wrong on both counts, and behavioural testing on Claude Code 2.1.222 proved it:

- **`commands/` files are loaded into the skill registry, not a separate command registry.** Verified with a control plugin containing only `commands/ctrlcmd.md` and no `skills/` directory: `claude plugin details` reported `Skills (1) ctrlcmd`. There is no "Commands" line in the component inventory at all.
- **So the wrapper did not create a command — it created a second skill named `spyglass`,** colliding with the real one in `skills/spyglass/`. `claude plugin details spyglass` showed `Skills (2) spyglass, spyglass`, one costing ~10.8k on-invoke tokens (the real workflow) and one ~90 (the three-line wrapper).

Plugin skills are addressed as `plugin:skill`. Spyglass is therefore invoked as **`/spyglass:spyglass`** — the same shape as `/superpowers:brainstorming`. A bare `/spyglass` never resolves, and no wrapper can make it.

In practice the explicit form is rarely typed: the skill's frontmatter `description` is a model-invoked trigger, so it engages on its own when Python implementation work begins.

### Agent definition format

Confirmed against installed plugins — note `tools` is a **comma-separated PascalCase list**, not a YAML array.

```markdown
---
name: codebase-searcher
description: Searches the existing project for functions, classes, or utilities that already provide the planned functionality, matching by concept rather than identifier
tools: Read, Grep, Glob
model: sonnet
color: blue
---

System prompt content here.
```

`name` and `description` are required. `tools` must be restricted to what the agent genuinely needs. `model` and `color` are optional.

**Never omit `tools` to mean "no tools".** An omitted `tools` key makes the agent **inherit the parent's entire toolset** — the opposite of a restriction. The frontmatter schema has no way to express an empty tool set, so an agent that genuinely needs nothing (`stdlib-searcher`, which reasons purely from training knowledge) is given the narrowest harmless grant — `tools: Read` — with a frontmatter comment recording why the key must not be deleted, and a body instruction forbidding its use.

Agents are referenced as `spyglass:<agent-name>`.

### Repository setup

Implementation includes standing up the repository itself, not only the plugin files.

**Location:** `~/Desktop/projects/spyglass/` — alongside the user's other projects.

**Spec home:** once the repo exists, this design spec moves into it at `docs/design-spec.md`. It currently lives at `~/.claude/docs/superpowers/specs/` only because this session ran outside any project, and that path is not a git repository — so the spec cannot be version-controlled where it sits.

**Additional files beyond the plugin tree:**

```
spyglass/
├── assets/
│   └── spyglass.png             # project image, referenced by README
├── .gitignore                   # standard Python/macOS ignores
├── README.md
└── LICENSE                      # MIT
```

**README structure:**

1. Project image (`assets/spyglass.png`)
2. One-line description
3. **The naming line**, immediately beneath the image — see The Name above
4. What it does — the problems-solved table, condensed
5. Installation — the two `/plugin` commands
6. Usage — the five invocation forms
7. What a run looks like — the phase flow, condensed, with the HIL checkpoints visible so users know it is interactive
8. Where artefacts go — `.claude/spyglass/`, and the note that the root `.gitignore` is never touched
9. Requirements — Python project; radon optional and never required
10. Licence

**Git setup:** initialise the repo, commit the plugin tree as the first commit, and confirm before any push to a remote. Publishing is the user's call, not an implementation step taken unasked.

**Local testing before publishing:** the plugin can be installed from a local path to verify it loads, the command registers, and the agents resolve — no marketplace round-trip needed to iterate.

---

## Artefact Storage

### Location

```
<project-root>/.claude/spyglass/
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

`.claude/` is already Claude Code's namespace within a project, which makes `.claude/spyglass/` the least surprising place for a Claude Code plugin to keep its own state. It requires no configuration and behaves identically in every repository.

### Git invisibility — without touching the user's files

On first run the skill writes `.claude/spyglass/.gitignore` containing a single line:

```
*
```

A `.gitignore` whose pattern matches everything, including itself, makes the entire directory invisible to git. This achieves gitignoring with **zero modification of any file the user owns** — the root `.gitignore` is never read, never appended to, never created.

This matters for a distributed plugin. The root `.gitignore` is tracked, shared, and often governed by team policy; a plugin that silently edits it produces an unexpected diff in the user's next commit, and in a monorepo may well edit the wrong one.

The skill announces this once, on the run that creates it: "Created `.claude/spyglass/` for design artefacts. It's self-ignored from git — your `.gitignore` was not modified."

If a user wants these artefacts committed, they delete that one file. The skill does not recreate it if the directory already exists.

### No-project fallback

Phase 1's project root discovery can fail — the skill may be invoked from a home directory or any non-project location. When no root marker is found:

- Artefacts go to `~/.claude/spyglass/`, same structure
- The skill states plainly which location it is using and why
- The self-ignoring `.gitignore` is still written, since `~/.claude/` is occasionally kept under version control

---

## Problems Solved

| Failure mode | How this skill addresses it |
|---|---|
| Reimplementing existing functionality | 4 parallel library investigation agents + synthesis |
| Ignoring codebase conventions | `pattern-analyzer` runs before contract design, constraining it |
| Oversized functions / classes | `style-checker` enforces Google style guide rules on the plan |
| Imports inside functions | Flagged post-implementation; module design enforces import grouping at planning stage |
| Refactoring never considered | Four detection signals auto-trigger assessment; adopted refactors are written into the plan |
| Tasks too large for one session | Two-phase scope assessment + persistent artefacts |
| No cross-session continuity | Artefact folder read at skill start, updated at end |
| Too many assumptions without user input | HIL checkpoints at every major decision point |

---

## Phase Flow

Phase numbers are labelled by design concern, not execution position. Phases 2 and 4 are each split because their halves belong at different points: scope needs a plan to judge (2a/2b), and pattern analysis needs a module design to target but must precede contract design (4a/4b).

**Execution order:**

```
Phase 1  — Context check           [Required]    Locate artefact dir, read index, detect orphans, generate slug
Phase 2a — Lightweight scope check [Required]    Obvious signal from task description
           └─ HIL-1 (batched): slug + prior context + scope signal
Phase 4a — Module design (L1)      [Required]    Files, responsibilities, call graph
Phase 3  — Pattern analysis        [Conditional] Targets directories named in L1
           └─ HIL-2: confirm L1 summary + patterns
Phase 4b — Contract + signature    [Required]    Levels 2-3, constrained by patterns
           └─ HIL-3: approve full plan → saved to pseudocode.md
Phase 2b — Scope re-check          [Required]    Judge scope against the actual plan
           └─ HIL-4: confirm scope and sub-task breakdown
Phase 5  — Library investigation   [Required]    4 agents in parallel (blocks until all complete)
Phase 6  — Investigation synthesis [Required]    use / partial / scratch recommendation
           └─ HIL-5: approve recommendation
           └─ HIL-5b [Conditional]: approve revised plan if re-plan triggered
Phase 7  — Style & principles      [Required]    Review pseudocode.md for violations
           └─ HIL-6: fix hard violations; select design violations to address
Phase 8  — Complexity assessment   [Conditional] Modifying existing files? Feeds refactor signal S1
Phase 9  — Refactor assessment     [Conditional] Auto-runs when any refactor signal fires
           └─ HIL-7: complexity report + recommendations + adoption selection
Phase 10 — Test planning           [Conditional] Auto-runs on complex contracts, or --tests
           └─ HIL-8: confirm test cases
Phase 11 — Artefact update         [Required]    Write index and session files
           └─ HIL-9: confirm content before writing
Phase 12 — Handoff                 [Required]    Present artefacts, choose next step
           └─ HIL-10: implement now / hand to writing-plans (if available) / stop here
```

### Fast-path

Evaluated before Phase 1, from the task description alone. Two variants, distinguished by whether the task adds new capability or changes existing behaviour — because library investigation only pays off for the former.

**`fast-path-modify`** — changes existing behaviour, introduces no new capability (add a parameter, fix an off-by-one, rename a symbol, adjust a threshold).
- Criteria: under 15 words AND names an existing function, class, or file AND introduces no new capability
- Skips: Phases 3, 5, 6, 10 and their HIL checkpoints
- Runs: 1, 2a, 4a, 4b, 2b, 7, 8, 9 (if signals fire), 11, 12
- Rationale: nothing new is being built, so there is nothing to investigate — but the code being touched may still warrant refactoring, so Phases 8 and 9 stay live

**`fast-path-add`** — adds a small new capability (one function, one small class).
- Criteria: under 15 words AND describes a single new function or small class
- Skips: Phases 3, 8, 10 and their HIL checkpoints
- Runs: 1, 2a, 4a, 4b, 2b, **reduced Phase 5**, 6, 7, 9 (if signals fire), 11, 12
- Reduced Phase 5 dispatches only `codebase-searcher` and `stdlib-searcher`. `deps-searcher` and `package-searcher` are skipped: adding a dependency for a trivial function is almost never right
- Rationale: "write a function that slugifies a string" is short *and* is exactly where reimplementation happens

Announce which variant applies and why. If neither matches, run the standard flow. When Phase 3 is skipped, Phases 4a and 4b run back to back as one planning step.

### HIL batching

HIL-1 combines Phase 1 and Phase 2a. HIL-2 combines a Level 1 module-design summary with the pattern report, so a wrong module design is catchable without a dedicated checkpoint. HIL-7 combines the complexity report with the refactor recommendations it produced. No other checkpoints are batched.

### `--complete` flow

1. Locate `<artefact-dir>/<feature-slug>/`. If not found, list available slugs from `PLANS_INDEX.md` and stop.
2. Read every file in the folder.
3. **Draft** `completed-summary.md` — what was built, decisions made, deviations from the plan, and any sub-tasks or deferred refactors left unfinished.
4. **Present the draft and wait for confirmation.**
5. On confirmation: write `completed-summary.md`, set status in `PLANS_INDEX.md` to `complete`, update `INDEX.md`.

No phase agents run. Confirmation always precedes both writes.

### Orphaned state recovery

Detected in Phase 1 when a folder exists with no `PLANS_INDEX.md` entry, or contains `pseudocode.md` but no `INDEX.md` — the signature of a session abandoned between Phase 4b and Phase 11.

Surface at HIL-1: "Found an incomplete plan for `[slug]` from a previous session. A pseudo-code plan already exists. Resume from it, or start fresh?"

- **Resume:** read the existing `pseudocode.md`, reconstruct the `INDEX.md` entry, continue from **Phase 2b**. Phases 4a, 3, and 4b are not re-run. Offer plan regeneration only if asked.
- **Start fresh:** archive to `<slug>-abandoned-<n>/` and begin from Phase 2a.

---

## Refactor Signal Detection

Refactor assessment is not something the user has to ask for. The skill watches for four signals during preceding phases and runs Phase 9 automatically when **any** fires.

| Signal | Source | Fires when |
|---|---|---|
| **S1 — Complexity in the change path** | Phase 8 | A function being modified has radon grade C or worse (cyclomatic complexity > 10) |
| **S2 — Near-duplicate existing code** | Phase 6 | The synthesiser recommends `partial-use` against **priority-1 codebase code** — existing code does most of the job, so unifying may beat building alongside it |
| **S3 — Plan pushes existing code over a limit** | Phase 4b + Phase 7 | The plan would take an existing class past 200 lines, or give a module a second distinct responsibility |
| **S4 — Inconsistent patterns in the target area** | Phase 3 | The pattern analyser reports `inconsistent` for any pattern in the directories being touched — new code cannot follow a convention that does not exist |

**Overrides:** `--refactor` forces Phase 9 without a signal; `--no-refactor` suppresses it despite one.

**When no signal fires and no keyword is given**, Phase 9 does not run and Phase 8's complexity report is folded into the Phase 12 summary — visible, without a checkpoint interrupting for a decision with nothing behind it.

Each fired signal is reported at HIL-7 with its evidence, so the user sees *why* the assessment ran.

---

## HIL Checkpoint Specifications

Each checkpoint presents a specific question and waits for user input. Checkpoints are not optional.

**HIL-1 (batched) — Slug, prior context, scope signal** *(after Phases 1 and 2a)*

Present in one message: the generated slug alongside existing slugs; relevant prior artefacts found; the orphaned-state prompt if detected; the artefact directory location if this run created it; the lightweight scope signal.

Ask: "Is this the right feature slug? Should any prior work listed be considered? Does the scope signal match your expectation?"

Wait for: slug confirmation or correction; relevance decision; scope confirmation.

**HIL-2 (batched) — Module design and patterns** *(after Phases 4a and 3)*

Present: a brief Level 1 summary — files to be created or modified and each one's responsibility — plus the pattern report with confidence levels.

**HIL-2 runs whether or not Phase 3 did.** When Phase 3 is skipped — greenfield directories, either fast path — only the pattern half drops: present the Level 1 summary alone, state why there is no pattern report, and confirm the structure. It is the only confirmation the Level 1 module design ever receives, and every Phase 4b contract is built on it.

Ask: "Here's the module structure I'm planning and the conventions I found in those directories. Does the structure look right, and are these patterns accurate?"

Wait for: confirmation or correction of both. Module-design corrections send Phase 4a back for revision before Phase 4b. Pattern corrections are authoritative and become hard constraints on Phase 4b.

**HIL-3 — Full plan approval** *(after Phase 4b)*

Present: the complete three-level planning document.

Ask: "Does this plan look right? Any functions, classes, or modules to add, remove, or redesign before we investigate libraries?"

Wait for: explicit approval or change requests. Do not proceed until approved — a wrong plan wastes all downstream agent work. `pseudocode.md` is written on approval.

**HIL-4 — Final scope and sub-task breakdown** *(after Phase 2b)*

Present: the scope judgment against the actual plan; if multi-session, the ordered sub-task list and which to implement now.

Ask: "Confirmed scope: [single-session / multi-session]. [If multi-session:] Does this breakdown look right, and should we start with [current-task]?"

Wait for: confirmation or reordering. Record any override.

**HIL-5 — Library recommendation approval** *(after Phase 6)*

Present: the recommendation with full justification and the priority-order reasoning behind it.

Ask: "This is my recommendation for how to approach the implementation. Do you agree, or do you want to override?"

Wait for: approval or override with reason. Record in `session-context.md`.

**HIL-5b — Revised plan approval** *(conditional — only if the re-plan trigger fires)*

Present: a diff of `pseudocode.md` against the pre-edit snapshot.

Ask: "The library recommendation required changes to the plan. Here's what changed — does the revised plan look right?"

Wait for: explicit approval. On approval, delete the snapshot. On rejection, restore from it and return to HIL-5. This reinstates the HIL-3 approval the re-plan invalidated.

**HIL-6 — Style violations** *(after Phase 7)*

Present hard violations (blocking) and design violations (advisory) as separate lists.

Ask: for hard violations, "Should I apply these fixes to the plan?"; for design violations, which to address.

Wait for: both decisions. Update `pseudocode.md` after.

**HIL-7 (batched) — Refactor findings and adoption** *(after Phases 8 and 9; conditional on a signal firing)*

Present in one message:
- **Why this ran** — which signals fired, with evidence (e.g. "S1: `parse_records` is radon grade D"; "S2: `utils.normalise_date` covers 70% of the planned `to_iso_date`")
- The complexity report, when Phase 8 ran
- Up to 5 recommendations, each with `order` and `risk`

Ask: "These refactors look warranted. Which do you want to adopt?"

Wait for: selection. Zero is valid.

**HIL-8 — Test plan confirmation** *(after Phase 10, conditional)*

Present: test cases per public function. Ask: "Does this test plan look complete? Any cases to add or remove?"

**HIL-9 — Artefact write confirmation** *(during Phase 11, before any write)*

Present: everything to be written — slug, session-context summary, future sub-tasks and deferred refactors, and the file list.

Ask: "I'm about to write this to `<artefact-dir>/[slug]/`. Does this look right? Any context to add or remove?"

Wait for: confirmation or edits. Write only after.

**HIL-10 — Handoff** *(after Phase 12 summary)*

Present: artefacts produced, approved recommendation, confirmed scope, adopted refactors.

Ask: "Design is complete. How do you want to proceed?"
- Implement now, in this session, following the approved plan
- Hand off to `superpowers:writing-plans` — **offered only when superpowers is installed**
- Stop here — artefacts are saved and resumable

Wait for: an explicit choice. Never begin implementing without one.

---

## Phase Specifications

*Ordered by execution sequence.*

### Phase 1 — Context Check

**Artefact directory resolution:**
1. Search upward from the working directory for `.git`, `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`. Prefer the directory containing `.git` when markers appear at multiple levels.
2. Found → artefact directory is `<project-root>/.claude/spyglass/`.
3. Not found → artefact directory is `~/.claude/spyglass/`. State this plainly.
4. If the directory does not exist, create it and write `.gitignore` containing `*`. Announce once (see Git invisibility).

**Steps:**
1. Read `PLANS_INDEX.md` if present; note its absence otherwise.
2. Identify feature folders semantically related to the current task — reason about relevance rather than matching strings.
3. For each, read `INDEX.md` to surface pending sub-tasks, session context, and deferred refactors.
4. Detect orphaned state. Surface at HIL-1 if found.
5. Generate the slug: lowercase, hyphens for spaces, stop words stripped, max 30 characters. Stop words are grammatical filler only — articles, prepositions, conjunctions, auxiliary verbs — and meaning-carrying nouns are kept even when the result is well under the cap. "Add CSV export to data pipeline" → `csv-export-data-pipeline`.

### Phase 2a — Lightweight Scope Check

By the main Claude instance, from the task description alone — no agent. Emits one signal: `trivial` | `small` | `medium` | `large` | `multi-session-likely`.

A signal, not a decision. The binding scope decision is HIL-4, after the plan exists.

*→ Batched into HIL-1.*

### Phase 4a — Module Design (Level 1)

By the main Claude instance. Held in context until HIL-3 approves the complete plan.

- Modules and files to create or modify, with directory paths
- Responsibility of each — one clear purpose per file
- Call graph: which modules depend on which
- Public interface vs. internal implementation split
- Import groups each module needs (stdlib / third-party / local), establishing at design time that imports belong at module top

The directory paths named here are what Phase 3 targets. This is why Level 1 precedes pattern analysis.

### Phase 3 — Pattern Analysis (`pattern-analyzer`) — Conditional

**Trigger:** Python files exist in any directory named in Level 1. Fully determinate — targets come from Level 1, not guesswork.

**File prioritisation (max 10, drawn from Level 1's directories):**
1. `__init__.py` in each target package
2. Files whose names are most similar to Level 1's planned filenames
3. Most recently modified (`git log --name-only -n 20`, or `ls -t` outside a repo)
4. Remainder up to the cap

**Output:** import style; naming conventions beyond PEP 8; class vs. module-level function preference; error handling patterns; docstring format (Google, NumPy, or Sphinx); project-specific conventions.

Confidence per pattern: `established` (3+ files) | `observed` (1–2) | `inconsistent` (contradictory — report both variants). Any `inconsistent` finding raises **signal S4**.

The file list and pattern report pass forward to `codebase-searcher`, so it does not re-read the same files.

→ **HIL-2**

### Phase 4b — Contract and Signature Design (Levels 2–3)

Constrained by patterns confirmed at HIL-2. Where a confirmed pattern conflicts with a style-guide default, the project pattern wins — except where it violates a Phase 7 hard rule.

**Level 2 — Contract design.** For each function and method, express only what a signature cannot:
- Name and owning module
- Preconditions and postconditions
- Edge cases and how each is handled
- Algorithm in prose: approach, data structures, key operations. No code.

Parameters, types, and return types are **not** restated — Level 3 renders them precisely. "Why this approach rather than alternatives" is answered in Phase 6, after investigation.

**Level 3 — Signature design.**
```python
def function_name(param: Type, param2: Type = default) -> ReturnType:
    """One-line summary of intent."""
```
Class skeletons with `__init__`, public methods, `@property` definitions. Level 2 is the design rationale; Level 3 is the interface contract implementation starts from.

**Constraints flagged here:** function > 40 lines of logic → redesign; class > 200 lines → split; a contract describing two distinct operations → split candidate.

**Existing-code impact check:** where the plan adds to an existing class or module, estimate resulting size. Exceeding 200 lines, or adding a second distinct responsibility, raises **signal S3**.

**Save:** on HIL-3 approval, Levels 1–3 written to `<artefact-dir>/<slug>/pseudocode.md`. This is the working document for the rest of the run.

→ **HIL-3**

### Phase 2b — Scope Re-check (`scope-assessor`)

**Input:** task description + approved `pseudocode.md` (Levels 1–2)

**Output:** `scope`; `sub_tasks` (ordered, if multi-session); `current_task`; `rationale`

**Heuristics against the actual plan:**
- Single-session: ≤ 3 new or modified *implementation* files (tests excluded), ≤ 5 new functions/classes, no schema or public interface changes
- Multi-session: new modules, schema changes, cross-cutting refactors, or > 5 new functions/classes

→ **HIL-4**

### Phase 5 — Library Investigation

Four agents dispatched in a single multi-tool-call response, running concurrently. Phase 6 blocks until all complete. Each reports "no findings" on failure rather than erroring. Under `fast-path-add`, only the first two run.

**`codebase-searcher`** — tools: `Read, Grep, Glob`
- Search project files for functions, classes, or utilities matching or approximating the planned functionality
- Search by concept, not identifier — reason about what code does, not what it is named
- Receives Phase 3's file list and pattern report when available, to avoid re-reading
- Fallback: "no existing codebase to search"
- Report: match quality (`exact` | `partial` | `related`), path, symbol, what it does, what gap remains

**`stdlib-searcher`** — tools: `Read` (narrowest harmless grant; the agent is forbidden to use it — see Agent definition format)
- Reasons from training knowledge; reads no files
- Priority modules: `itertools`, `functools`, `collections`, `pathlib`, `contextlib`, `dataclasses`, `typing`, `abc`, `enum`, `datetime`, `io`, `os`, `re`, `json`, `csv`, `logging`, `threading`, `concurrent.futures`, `unittest.mock`
- Report: module, relevant class/function, what it provides, what it does not cover

**`deps-searcher`** — tools: `Read, Glob, Bash`
- Run `pip freeze` for the actually-installed list — more reliable than declaration files, which miss editable installs and drift
- Also read `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` for declared constraints
- Fallback: "no dependency information found"
- Report: package, installed version, relevant API surface, what gap remains

**`package-searcher`** — tools: `WebSearch, WebFetch`
- Search PyPI for packages not currently installed
- Download counts: fetch `https://pypistats.org/api/packages/<name>/recent` — PyPI pages do not publish these, and an unsourced number will be invented
- CVE check: fetch `https://osv.dev/list?ecosystem=PyPI&q=<pkg>`. WebFetch is GET-only and cannot send a request body, so the OSV JSON query API is unreachable with these tools; the GET-able advisory list is what the agent can actually read. A status that cannot be verified is reported as `unverified`, never `clean`
- Fallback: "PyPI search unavailable"

**Hard disqualifiers** — never recommend a package failing any:
  - No release within 18 months
  - Non-permissive licence (anything other than MIT, Apache 2.0, BSD, or similar)
  - Unresolved critical CVE in the OSV response

**Reporting floor** — do not surface below this, to avoid typosquats and abandoned toys:
  - ≥ 500 GitHub stars OR ≥ 10k monthly downloads

**Adoption as evidence, not a gate** — report stars, downloads, last release, maintainer count for the synthesiser and user to weigh. Adoption is a judgment input, not a safety property; an AND-gate on stars and downloads would reject well-maintained narrow-purpose packages that are often correct.

### Phase 6 — Investigation Synthesis (`investigation-synthesiser`)

**Input:** all dispatched agents' reports; partial sets accepted, missing sources noted.

**Priority order:**
1. Existing codebase — no new dependency, already understood
2. Python stdlib — zero cost, zero dependency
3. Already-installed package — dependency already paid for
4. New PyPI package — lowest, adds a dependency

**Output:** exactly one recommendation.

| Recommendation | Meaning |
|---|---|
| `use-existing` | A source at priority 1–3 covers the requirement fully |
| `partial-use` | Best source covers part; specify precisely what to use and what to implement |
| `implement-from-scratch` | No source fits; justify each rejection individually |

**A `partial-use` must specify:** which source at which priority and for what; what it does not cover and why; where custom code wraps or extends it; integration risks; why this approach over the alternatives — answering Phase 4b's deferred "why".

**Refactor signal:** `partial-use` against **priority-1 codebase code** raises **S2**. Existing code doing most of the job is the classic case where generalising it beats building a parallel implementation — but that is a refactor, and should be assessed as one rather than assumed.

**Scope change definition:** adds a file not in the plan, removes a module boundary, or changes planned function count by more than 2. Same-interface algorithmic changes update the Level 2 algorithm description only.

**Re-plan trigger:** when the scope-change definition is met:
1. Copy `pseudocode.md` to `pseudocode.prev.md` — the snapshot HIL-5b diffs against and restores from
2. Apply revisions in place
3. Present the diff at HIL-5b

→ **HIL-5**, then **HIL-5b** if re-plan fired.

### Phase 7 — Style & Principles Review (`style-checker`)

Reviews `pseudocode.md`. Checks only what pseudo-code can reveal.

**Hard violations — blocking:**
- Function estimated at > 40 lines of logic
- Class estimated at > 200 lines total
- `staticmethod` where a module-level function would serve
- Mutable default arguments in Level 3 signatures (e.g. `def f(x: list = [])`)

**Design violations — advisory:**
- A contract describing two distinct operations. Judge the operations, not the word "and" — "validates the input and returns the parsed record" is one responsibility; "writes the record to disk and sends a notification email" is two
- Function name does not clearly describe what it does
- Public function lacks type annotations
- Public function lacks a docstring
- Class does more than one thing

**Deferred to post-implementation — do not flag here:** imports inside functions; bare `except:` or catching `Exception` without re-raising; `__double_underscore__` misuse. These are invisible in pseudo-code, and flagging them produces noise that trains the user to rubber-stamp the checkpoint.

Confirms or clears **S3** using the post-HIL-6 state — a hard-violation fix may already have resolved the size problem that raised it.

**Reference:** `python-standards.md`. The main instance must pass its **absolute path**, resolved from the skill's own directory — the agent's working directory is the user's project, where a relative path to the plugin's files does not resolve. With no usable path the agent falls back to its inline rules and says so.

→ **HIL-6**

### Phase 8 — Complexity Assessment (`complexity-assessor`) — Conditional

**Trigger:** the task modifies existing Python files rather than being purely net-new.

**Mechanism — measure with a tool, interpret with an agent; the agent owns both.** It has `Bash` and `Read`, so the main instance hands over file paths and nothing else — no radon output, no file contents piped through its context.
1. The agent runs `radon cc <file> -s` for each file being modified
2. If radon is absent, it falls back to reading the files and assessing by eye, noting the figures are estimates. Never prompt to install — environment setup is not this plugin's business
3. The main instance passes the list of file paths plus `module_design`
4. The agent adds nesting-depth assessment and identifies functions in the change path

**Output:** per-function complexity for touched functions. Grade C or worse (complexity > 10) raises **S1**.

No HIL of its own. If S1 fires, the report is evidence at HIL-7. If nothing fires, it folds into the Phase 12 summary.

### Phase 9 — Refactor Assessment (`refactor-assessor`) — Conditional

**Trigger:** any of S1–S4 fired, or `--refactor`. Suppressed by `--no-refactor`.

Not user-initiated in normal use — the skill decides refactoring is worth assessing from what preceding phases observed.

**Input:** fired signals with evidence, `pseudocode.md`, complexity report (if run), pattern report (if run).

**Scope cap:** maximum 5 recommendations, restricted to files the task already touches. If more candidates exist, report the count dropped rather than silently truncating.

**Output per recommendation:** file and function; motivating signal; the problem; specific approach (extract function, split class, generalise existing function to absorb the new case, unify duplicates, flatten nesting); `order` (`before-current-task` | `after-current-task`); `risk` (`low` internal only | `medium` changes signatures | `high` changes public API or module boundary).

**Where adopted recommendations are destined** — this is what makes the assessment consequential rather than advisory. Phase 9 decides destinations; the writes happen in Phase 11, after HIL-9 confirms:

- **`before-current-task`** → a *Preliminary refactors* section at the top of Level 1 in `pseudocode.md`. Implementation performs these first, so new code lands on sound structure.
- **`after-current-task`** → `future-tasks.md`, with motivating signal and evidence, so a future session understands why it was raised. Produced even on a single-session run.
- **Not adopted** → `session-context.md`, with its signal and the fact the user declined, so it is not re-litigated from scratch next session.

→ **HIL-7**

### Phase 10 — Test Planning (`test-planner`) — Conditional

**Trigger:** `--tests`, or the contract doc contains ≥ 3 edge cases for a single function or any function with > 2 preconditions.

**Framework detection, before generating any case:**
1. `pyproject.toml` for `[tool.pytest.ini_options]`
2. `pytest.ini`, `setup.cfg [tool:pytest]`, `tox.ini`
3. Scan the test directory for class-based (`unittest.TestCase`) vs. function-based structure
4. Default to pytest when ambiguous

**Output per public function, in the detected framework's conventions:** happy-path cases; edge cases from contract preconditions; error conditions with the expected exception; naming `test_<function>_<scenario>` (pytest) or the same as a method on a `TestCase` subclass (unittest).

Described in prose, not implemented. Saved to `test-plan.md` after HIL-8.

→ **HIL-8**

### Phase 11 — Artefact Update

**Status vocabularies** — declared so they do not drift between sessions.

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

**`PLANS_INDEX.md`:**
```markdown
# Plans Index

| Folder | Description | Status |
|--------|-------------|--------|
| csv-export-data-pipeline | CSV export for data pipeline | in-progress |
| auth-refactor | JWT auth middleware replacement | complete |
```

**`<feature>/INDEX.md`** — optional files appear as `not-run` when skipped:
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

**Single-session success path:** writes `session-context.md`, sets `PLANS_INDEX.md` to `session-done`. `future-tasks.md` only if deferred refactors exist. `INDEX.md` marks present files `current`, absent optional files `not-run`. Status becomes `complete` only via `--complete`.

**`session-context.md`** — written by the main Claude instance after HIL-9 confirms content:
- Key decisions and reasons, especially HIL overrides
- Technical context future sessions need — schemas, constraints, interface contracts
- Refactor recommendations declined, with motivating signal
- Remaining sub-tasks and order (multi-session only)

**`user_overrides` entry format:**
```
hil:           HIL number where the override occurred
recommended:   What the agent recommended
chosen:        What the user chose instead
reason:        User's stated reason, or "no reason given"
```

**Feature slug consistency:** at HIL-1, always show the generated slug alongside existing ones, so a re-phrased task can be pointed at the folder it belongs to. Consistency comes from explicit confirmation, not algorithmic matching.

→ **HIL-9**

### Phase 12 — Handoff

Present a closing summary: artefacts written with paths; the approved recommendation in one line; confirmed scope and current sub-task; adopted refactors split by `order`; the complexity report if Phase 8 ran but no signal fired; count of unresolved design violations.

**Availability check:** offer the `superpowers:writing-plans` handoff only if superpowers is installed. Detect by checking whether the skill is available; if not, present only implement-now and stop-here. The plugin must be fully functional standalone.

→ **HIL-10**

The skill never begins implementing on its own. Its output is a design; the decision to act on it is always the user's.

---

## Agent Summary

Referenced as `spyglass:<name>`.

| Agent | Tools | Runs in |
|---|---|---|
| `pattern-analyzer` | Read, Grep, Glob, Bash | Phase 3 (conditional) |
| `scope-assessor` | Read | Phase 2b |
| `codebase-searcher` | Read, Grep, Glob | Phase 5 |
| `stdlib-searcher` | Read (unused — narrowest grant, since omitting `tools` inherits everything) | Phase 5 |
| `deps-searcher` | Read, Glob, Bash | Phase 5 |
| `package-searcher` | WebSearch, WebFetch | Phase 5 |
| `investigation-synthesiser` | Read | Phase 6 |
| `style-checker` | Read | Phase 7 |
| `complexity-assessor` | Read, Bash | Phase 8 (conditional) |
| `refactor-assessor` | Read, Grep | Phase 9 (signal-driven) |
| `test-planner` | Read, Glob | Phase 10 (conditional) |

---

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

---

## Open Questions

None — all design decisions resolved.
