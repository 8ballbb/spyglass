---
name: spyglass
description: Use when implementing any Python feature, function, class, or module, before writing implementation code
---

# Spyglass

Structured design analysis before any Python implementation. It prevents reimplementing functionality that already exists, ignoring codebase conventions, writing oversized functions and classes, never considering refactoring, and starting tasks too large for one session. Twelve phases, ten human-in-the-loop checkpoints, and a set of persistent artefacts that make a design resumable across sessions.

**Announce at start, verbatim:**

> I'm using the spyglass skill to design this before writing code.

**Terminal state.** This skill produces design artefacts and stops at Phase 12. It does not implement. Implementation happens only after an explicit choice at HIL-10 — never on the skill's own initiative, and never as an inferred continuation.

**Invocation keywords** — recognised in the invocation text, not CLI flags: `--tests` forces test planning (Phase 10); `--refactor` forces refactor assessment even when no signal fires; `--no-refactor` suppresses it even when signals fire; `--complete <feature-slug>` marks a feature complete and writes its summary. Scope: Python projects only.

## Artefact Directory Resolution

1. Search upward from the working directory for `.git`, `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`. Prefer the directory containing `.git` when markers appear at multiple levels.
2. Found → artefact directory is `<project-root>/.claude/spyglass/`.
3. Not found → artefact directory is `~/.claude/spyglass/`. State this plainly to the user.
4. If the directory does not exist, create it and write `.gitignore` containing a single line: `*`.

A `.gitignore` whose pattern matches everything, including itself, makes the whole tree invisible to git with **zero modification of any file the user owns**. On the run that creates it, announce once, verbatim except for `<artefact-dir>`, which is substituted with the location actually resolved above — `.claude/spyglass/` in a project, `~/.claude/spyglass/` under the no-project fallback:

> Created `<artefact-dir>` for design artefacts. It's self-ignored from git — your `.gitignore` was not modified.

**Hard rules:**

- **Never read, create, or modify the project's root `.gitignore`.** It is tracked, shared, often governed by team policy, and in a monorepo the wrong one is easy to pick. Spyglass ships to strangers; it leaves their files alone.
- **Do not recreate `.claude/spyglass/.gitignore` if the directory already exists.** A user who deleted it wants these artefacts committed.
- The self-ignoring `.gitignore` is still written under the `~/.claude/spyglass/` fallback, since `~/.claude/` is occasionally kept under version control.

## Fast-path

Evaluated **before Phase 1**, from the task description alone. Two variants, distinguished by whether the task adds new capability or changes existing behaviour — library investigation only pays off for the former.

**`fast-path-modify`** — changes existing behaviour, introduces no new capability (add a parameter, fix an off-by-one, rename a symbol, adjust a threshold).
- Criteria: under 15 words AND names an existing function, class, or file AND introduces no new capability
- Skips: Phases 3, 5, 6, 10 and their HIL checkpoints — but **HIL-2 still runs**, on the Level 1 summary alone
- Runs: 1, 2a, 4a, 4b, 2b, 7, 8, 9 (if signals fire), 11, 12
- Rationale: nothing new is being built, so there is nothing to investigate — but the code being touched may still warrant refactoring, so Phases 8 and 9 stay live

**`fast-path-add`** — adds a small new capability (one function, one small class).
- Criteria: under 15 words AND describes a single new function or small class
- Skips: Phases 3, 8, 10 and their HIL checkpoints — but **HIL-2 still runs**, on the Level 1 summary alone
- Runs: 1, 2a, 4a, 4b, 2b, **reduced Phase 5**, 6, 7, 9 (if signals fire), 11, 12
- **Reduced Phase 5 dispatches only `spyglass:codebase-searcher` and `spyglass:stdlib-searcher`.** `spyglass:deps-searcher` and `spyglass:package-searcher` are skipped: adding a dependency for a trivial function is almost never right
- Rationale: "write a function that slugifies a string" is short *and* is exactly where reimplementation happens

**Announce which variant applies and why.** If neither matches, run the standard flow. When Phase 3 is skipped, Phase 4b follows Phase 4a directly as one planning step — with HIL-2 still between them, confirming the Level 1 summary without a pattern report.

## Phase Flow

```
Phase 1  — Context check           [Required]    Locate artefact dir, read index, detect orphans, generate slug
Phase 2a — Lightweight scope check [Required]    Obvious signal from task description
           └─ HIL-1 (batched): slug + prior context + scope signal
Phase 4a — Module design (L1)      [Required]    Files, responsibilities, call graph
Phase 3  — Pattern analysis        [Conditional] Targets directories named in L1
           └─ HIL-2 [Required]: confirm L1 summary + patterns (L1 alone if Phase 3 skipped)
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

**The numbering is not an error.** Phase numbers label design concerns, not execution positions. Phases 2 and 4 are each split because their halves belong at different points: scope needs a plan to judge (2a/2b), and pattern analysis needs a module design to target but must precede contract design (4a/4b).

**HIL batching:** HIL-1 combines Phase 1 and Phase 2a. HIL-2 combines the Level 1 module-design summary with the pattern report. HIL-7 combines the complexity report with the refactor recommendations it produced. No other checkpoints are batched.

## Phase Specifications

*In execution order.*

### Phase 1 — Context Check — Required

No agent; main instance. Resolve the artefact directory (above), then: (1) read `PLANS_INDEX.md` if present, noting its absence otherwise; (2) identify feature folders semantically related to the current task — reason about relevance rather than matching strings; (3) for each, read `INDEX.md` to surface pending sub-tasks, session context, and deferred refactors; (4) detect orphaned state (see Orphaned State Recovery), surfacing it at HIL-1 if found; (5) generate the slug — lowercase, hyphens for spaces, stop words stripped, max 30 characters. Stop words are the grammatical filler only — articles, prepositions, conjunctions, and auxiliary verbs (`a`, `the`, `to`, `for`, `of`, `in`, `and`, `add`). Nouns that carry meaning are kept, even when the result is well under the cap: "Add CSV export to data pipeline" → `csv-export-data-pipeline`.

→ batched into **HIL-1**

### Phase 2a — Lightweight Scope Check — Required

No agent; main instance, from the task description alone. Emits one signal: `trivial` | `small` | `medium` | `large` | `multi-session-likely`. A signal, not a decision — the binding scope decision is HIL-4, after the plan exists.

→ batched into **HIL-1**

### Phase 4a — Module Design (Level 1) — Required

No agent; main instance. **Produces Level 1 only, held in context.** `pseudocode.md` is not written here — it is written on HIL-3 approval, after Levels 2–3 exist.

Level 1 covers: modules and files to create or modify, with directory paths; the responsibility of each — one clear purpose per file; the call graph, i.e. which modules depend on which; the public interface vs. internal implementation split; and the import groups each module needs (stdlib / third-party / local), establishing at design time that imports belong at module top.

The directory paths named here are what Phase 3 targets. This is why Level 1 precedes pattern analysis.

### Phase 3 — Pattern Analysis — Conditional — `spyglass:pattern-analyzer`

**Trigger:** Python files exist in any directory named in Level 1. Fully determinate — targets come from Level 1, not guesswork.

**Receives:** the Level 1 directory list and planned filenames.

**File prioritisation (max 10, drawn from Level 1's directories):** (1) `__init__.py` in each target package; (2) files whose names are most similar to Level 1's planned filenames; (3) most recently modified (`git log --name-only -n 20`, or `ls -t` outside a repo); (4) remainder up to the cap.

**Output:** import style; naming conventions beyond PEP 8; class vs. module-level function preference; error handling patterns; docstring format (Google, NumPy, or Sphinx); project-specific conventions. Confidence per pattern: `established` (3+ files) | `observed` (1–2) | `inconsistent` (contradictory — report both variants). Any `inconsistent` finding raises **signal S4**.

The file list and pattern report pass forward to `spyglass:codebase-searcher`, so it does not re-read the same files.

→ **HIL-2**

### Phase 4b — Contract and Signature Design (Levels 2–3) — Required

No agent; main instance. Constrained by patterns confirmed at HIL-2. Where a confirmed pattern conflicts with a style-guide default, the project pattern wins — except where it violates a Phase 7 hard rule.

**Level 2 — Contract design.** For each function and method, express only what a signature cannot: name and owning module; preconditions and postconditions; edge cases and how each is handled; algorithm in prose (approach, data structures, key operations — no code). Parameters, types, and return types are **not** restated; Level 3 renders them precisely. "Why this approach rather than alternatives" is answered in Phase 6, after investigation.

**Level 3 — Signature design.**
```python
def function_name(param: Type, param2: Type = default) -> ReturnType:
    """One-line summary of intent."""
```
Plus class skeletons with `__init__`, public methods, and `@property` definitions. Level 2 is the design rationale; Level 3 is the interface contract implementation starts from.

**Constraints flagged here:** function > 40 lines of logic → redesign; class > 200 lines → split; a contract describing two distinct operations → split candidate.

**Existing-code impact check:** where the plan adds to an existing class or module, estimate resulting size. Exceeding 200 lines, or adding a second distinct responsibility, raises **signal S3**.

**Save:** on HIL-3 approval, Levels 1–3 are written to `<artefact-dir>/<slug>/pseudocode.md`. This is the working document for the rest of the run.

→ **HIL-3**

### Phase 2b — Scope Re-check — Required — `spyglass:scope-assessor`

**Receives:** task description + approved `pseudocode.md` (Levels 1–2). **Output:** `scope`; `sub_tasks` (ordered, if multi-session); `current_task`; `rationale`.

**Heuristics against the actual plan:**
- Single-session: ≤ 3 new or modified *implementation* files (tests excluded), ≤ 5 new functions/classes, no schema or public interface changes
- Multi-session: new modules, schema changes, cross-cutting refactors, or > 5 new functions/classes

→ **HIL-4**

### Phase 5 — Library Investigation — Required

**Dispatch all four agents in a single response** so they run concurrently. Phase 6 blocks until all have returned. Each reports "no findings" on failure rather than erroring. Under `fast-path-add`, only the first two run.

**Receives (every agent):** `task_description` and the approved plan — **all three levels** of `pseudocode.md`. Level 1 alone is not enough: Levels 2 and 3 hold the contracts and signatures a searcher needs to judge whether a candidate actually fits, rather than merely sounding related.

- **`spyglass:codebase-searcher`** — searches project files for functions, classes, or utilities matching or approximating the planned functionality, by concept rather than identifier. Also receives Phase 3's file list and pattern report when available. Reports match quality (`exact` | `partial` | `related`), path, symbol, what it does, what gap remains.
- **`spyglass:stdlib-searcher`** — reasons from training knowledge, reads no files. Reports module, relevant class/function, what it provides, what it does not cover.
- **`spyglass:deps-searcher`** — inspects installed and declared dependencies. Reports package, installed version, relevant API surface, what gap remains.
- **`spyglass:package-searcher`** — searches PyPI for packages not installed, with download counts and CVE checks. Applies the hard disqualifiers (no release within 18 months; non-permissive licence; unresolved critical CVE) and the reporting floor (≥ 500 GitHub stars OR ≥ 10k monthly downloads). Adoption is evidence for the synthesiser to weigh, not a gate.

No HIL of its own.

### Phase 6 — Investigation Synthesis — Required — `spyglass:investigation-synthesiser`

**Receives:** all dispatched agents' reports; partial sets accepted, missing sources noted.

**Priority order:** 1. existing codebase (no new dependency, already understood) → 2. Python stdlib (zero cost) → 3. already-installed package (dependency already paid for) → 4. new PyPI package (lowest — adds a dependency).

**Output:** exactly one recommendation — `use-existing` (a source at priority 1–3 covers the requirement fully), `partial-use` (best source covers part; specify precisely what to use and what to implement), or `implement-from-scratch` (no source fits; justify each rejection individually).

A `partial-use` must specify: which source at which priority and for what; what it does not cover and why; where custom code wraps or extends it; integration risks; why this approach over the alternatives — answering Phase 4b's deferred "why".

**Refactor signal:** `partial-use` against **priority-1 codebase code** raises **S2**.

**Scope change definition:** adds a file not in the plan, removes a module boundary, or changes planned function count by more than 2. Same-interface algorithmic changes update the Level 2 algorithm description only.

**Re-plan trigger** — when the scope-change definition is met: (1) copy `pseudocode.md` to `pseudocode.prev.md`, the snapshot HIL-5b diffs against and restores from; (2) apply revisions in place; (3) present the diff at HIL-5b.

→ **HIL-5**, then **HIL-5b** if the re-plan fired.

### Phase 7 — Style & Principles Review — Required — `spyglass:style-checker`

**Receives:** `pseudocode_doc_path`, and `standards_path` — the **absolute path** to `python-standards.md`, resolved from this skill's own directory (it is a sibling of this file). Resolve and pass it explicitly: the agent runs with the *user's project* as its working directory, where a relative path to the plugin's own files does not exist, so without an absolute path the rulebook is simply unreadable. Checks only what pseudo-code can reveal.

**Hard violations — blocking:** function estimated at > 40 lines of logic; class estimated at > 200 lines total; `staticmethod` where a module-level function would serve; mutable default arguments in Level 3 signatures.

**Design violations — advisory:** a contract describing two distinct operations (judge the operations, not the word "and"); function name does not clearly describe what it does; public function lacks type annotations; public function lacks a docstring; class does more than one thing.

**Deferred to post-implementation — do not flag here:** imports inside functions; bare `except:` or catching `Exception` without re-raising; `__double_underscore__` misuse. These are invisible in pseudo-code, and flagging them trains the user to rubber-stamp the checkpoint.

Confirms or clears **S3** using the post-HIL-6 state — a hard-violation fix may already have resolved the size problem that raised it.

→ **HIL-6**

### Phase 8 — Complexity Assessment — Conditional — `spyglass:complexity-assessor`

**Trigger:** the task modifies existing Python files rather than being purely net-new.

**Receives:** the list of existing Python file **paths** the task will modify, and `module_design` so the agent knows which functions sit in the change path. Pass paths, not file contents — the agent has `Read` and fetches what it needs itself.

**Measure with a tool, interpret with an agent — the agent owns both.** It has `Bash`: it runs `radon cc <file> -s` for each file itself. The main instance does not run radon and does not pipe radon output or file contents through its own context. If radon is absent, the agent falls back to reading the files and assessing by eye, noting that the figures are estimates and that radon would improve accuracy — **never prompt to install**, environment setup is not this plugin's business. The agent then adds what radon does not measure: nesting depth, and which functions the change actually touches.

**Output:** per-function complexity for touched functions. Grade C or worse (complexity > 10) raises **S1**.

No HIL of its own. If S1 fires, the report is evidence at HIL-7. If nothing fires, it folds into the Phase 12 summary.

### Phase 9 — Refactor Assessment — Conditional — `spyglass:refactor-assessor`

**Trigger:** any of S1–S4 fired, or `--refactor`. Suppressed by `--no-refactor`. Not user-initiated in normal use.

**Receives:** fired signals with evidence, `pseudocode.md`, complexity report (if run), pattern report (if run). **Scope cap:** maximum 5 recommendations, restricted to files the task already touches. If more candidates exist, report the count dropped rather than silently truncating.

**Output per recommendation:** file and function; motivating signal; the problem; specific approach (extract function, split class, generalise existing function to absorb the new case, unify duplicates, flatten nesting); `order` (`before-current-task` | `after-current-task`); `risk` (`low` internal only | `medium` changes signatures | `high` changes public API or module boundary).

**Where adopted recommendations are destined** — this phase decides destinations, it does not write. Every file below is written in Phase 11, after HIL-9 confirms:
- **`before-current-task`** → destined for a *Preliminary refactors* section at the top of Level 1 in `pseudocode.md`, so implementation performs these first and new code lands on sound structure
- **`after-current-task`** → destined for `future-tasks.md`, with motivating signal and evidence. That file is produced even on a single-session run
- **Not adopted** → recorded for `session-context.md` with its signal and the fact the user declined, so it is not re-litigated next session

→ **HIL-7**

### Phase 10 — Test Planning — Conditional — `spyglass:test-planner`

**Trigger:** `--tests`, or the contract doc contains ≥ 3 edge cases for a single function, or any function with > 2 preconditions.

**Framework detection, before generating any case:** `pyproject.toml` for `[tool.pytest.ini_options]` → `pytest.ini`, `setup.cfg [tool:pytest]`, `tox.ini` → scan the test directory for class-based (`unittest.TestCase`) vs. function-based structure → default to pytest when ambiguous.

**Output per public function, in the detected framework's conventions:** happy-path cases; edge cases from contract preconditions; error conditions with the expected exception; naming `test_<function>_<scenario>` (pytest) or the same as a method on a `TestCase` subclass (unittest). Described in prose, not implemented. Saved to `test-plan.md` **after** HIL-8.

→ **HIL-8**

### Phase 11 — Artefact Update — Required

No agent; main instance. Content is confirmed at HIL-9 **before any write**. Read `artefact-formats.md` before writing anything — it carries the status vocabularies, templates, and file contents.

**Phase 11 owns every write in the run**, except three that are explicitly gated at their own checkpoints: `pseudocode.md` on HIL-3 approval, `pseudocode.md` again after HIL-6 resolves style violations, and `test-plan.md` after HIL-8. Everything else — `PLANS_INDEX.md`, `INDEX.md`, `session-context.md`, `future-tasks.md`, and the *Preliminary refactors* section adopted at HIL-7 — is written here and nowhere earlier. Earlier phases name destinations; this phase performs the writes.

→ **HIL-9**

### Phase 12 — Handoff — Required

No agent; main instance. Present a closing summary: artefacts written with paths; the approved recommendation in one line; confirmed scope and current sub-task; adopted refactors split by `order`; the complexity report if Phase 8 ran but no signal fired; count of unresolved design violations.

**Availability check.** Offer the `superpowers:writing-plans` handoff **only if superpowers is installed** — detect by checking whether that skill is available. If it is not, present only implement-now and stop-here. The plugin must be fully functional standalone; never tell the user to install superpowers.

→ **HIL-10**. The skill never begins implementing on its own. Its output is a design; the decision to act on it is always the user's.

## Refactor Signal Detection

Refactor assessment is not something the user has to ask for. Watch for four signals during the preceding phases and run Phase 9 automatically when **any** fires.

| Signal | Source | Fires when |
|---|---|---|
| **S1 — Complexity in the change path** | Phase 8 | A function being modified has radon grade C or worse (cyclomatic complexity > 10) |
| **S2 — Near-duplicate existing code** | Phase 6 | The synthesiser recommends `partial-use` against **priority-1 codebase code** — existing code does most of the job, so unifying may beat building alongside it |
| **S3 — Plan pushes existing code over a limit** | Phase 4b + Phase 7 | The plan would take an existing class past 200 lines, or give a module a second distinct responsibility |
| **S4 — Inconsistent patterns in the target area** | Phase 3 | The pattern analyser reports `inconsistent` for any pattern in the directories being touched — new code cannot follow a convention that does not exist |

**Overrides:** `--refactor` forces Phase 9 without a signal; `--no-refactor` suppresses it despite one.

**When no signal fires and no keyword is given:** Phase 9 does not run, and Phase 8's complexity report folds into the Phase 12 summary — visible, without a checkpoint interrupting for a decision with nothing behind it.

Each fired signal is reported at HIL-7 with its evidence, so the user sees *why* the assessment ran.

## HIL Checkpoint Specifications

**Each checkpoint waits for user input before proceeding. Checkpoints are not optional. Do not batch, skip, or infer an answer to any checkpoint the user has not given.**

### HIL-1 (batched) — Slug, prior context, scope signal *(after Phases 1 and 2a)*

**Present** in one message: the generated slug alongside existing slugs; relevant prior artefacts found; the orphaned-state prompt if detected; the artefact directory location if this run created it; the lightweight scope signal.

**Ask:** "Is this the right feature slug? Should any prior work listed be considered? Does the scope signal match your expectation?"

**Wait for:** slug confirmation or correction; relevance decision; scope confirmation.

### HIL-2 (batched) — Module design and patterns *(after Phases 4a and 3)*

**Present:** a brief Level 1 summary — files to be created or modified and each one's responsibility — plus the pattern report with confidence levels.

**Ask:** "Here's the module structure I'm planning and the conventions I found in those directories. Does the structure look right, and are these patterns accurate?"

**Wait for:** confirmation or correction of both. Module-design corrections send Phase 4a back for revision before Phase 4b. Pattern corrections are authoritative and become hard constraints on Phase 4b.

**When Phase 3 did not run** — a greenfield directory with no Python files, or either fast path — **HIL-2 still happens.** Only the pattern half drops. Present the Level 1 summary alone, say plainly why there is no pattern report ("no existing Python in the target directories" or "fast path"), and ask only: "Does the module structure look right?" This checkpoint is the sole confirmation the Level 1 module design ever gets, and Level 1 is what Phase 4b builds every contract on — skipping it would send an unconfirmed structure all the way to HIL-3.

### HIL-3 — Full plan approval *(after Phase 4b)*

**Present:** the complete three-level planning document.

**Ask:** "Does this plan look right? Any functions, classes, or modules to add, remove, or redesign before we investigate libraries?"

**Wait for:** explicit approval or change requests. Do not proceed until approved — a wrong plan wastes all downstream agent work. `pseudocode.md` is written **on approval**, not before.

### HIL-4 — Final scope and sub-task breakdown *(after Phase 2b)*

**Present:** the scope judgment against the actual plan; if multi-session, the ordered sub-task list and which to implement now.

**Ask:** "Confirmed scope: [single-session / multi-session]. [If multi-session:] Does this breakdown look right, and should we start with [current-task]?"

**Wait for:** confirmation or reordering. Record any override.

### HIL-5 — Library recommendation approval *(after Phase 6)*

**Present:** the recommendation with full justification and the priority-order reasoning behind it.

**Ask:** "This is my recommendation for how to approach the implementation. Do you agree, or do you want to override?"

**Wait for:** approval or override with reason. Record in `session-context.md`.

### HIL-5b — Revised plan approval *(conditional — only if the re-plan trigger fired)*

**Present:** a diff of `pseudocode.md` against the pre-edit snapshot `pseudocode.prev.md`.

**Ask:** "The library recommendation required changes to the plan. Here's what changed — does the revised plan look right?"

**Wait for:** explicit approval. On approval, delete the snapshot. On rejection, restore from it and return to HIL-5. This reinstates the HIL-3 approval that the re-plan invalidated.

### HIL-6 — Style violations *(after Phase 7)*

**Present:** hard violations (blocking) and design violations (advisory) as separate lists.

**Ask:** for hard violations, "Should I apply these fixes to the plan?"; for design violations, which to address.

**Wait for:** both decisions. Update `pseudocode.md` after.

### HIL-7 (batched) — Refactor findings and adoption *(after Phases 8 and 9; conditional on a signal firing)*

**Present** in one message:
- **Why this ran** — which signals fired, with evidence (e.g. "S1: `parse_records` is radon grade D"; "S2: `utils.normalise_date` covers 70% of the planned `to_iso_date`")
- The complexity report, when Phase 8 ran
- Up to 5 recommendations, each with `order` and `risk`

**Ask:** "These refactors look warranted. Which do you want to adopt?"

**Wait for:** selection. Zero is valid.

### HIL-8 — Test plan confirmation *(after Phase 10; conditional)*

**Present:** test cases per public function.

**Ask:** "Does this test plan look complete? Any cases to add or remove?"

**Wait for:** confirmation or edits. `test-plan.md` is written only after.

### HIL-9 — Artefact write confirmation *(during Phase 11, before any write)*

**Present:** everything to be written — slug, session-context summary, future sub-tasks and deferred refactors, and the file list.

**Ask:** "I'm about to write this to `<artefact-dir>/[slug]/`. Does this look right? Any context to add or remove?"

**Wait for:** confirmation or edits. Write only after.

### HIL-10 — Handoff *(after the Phase 12 summary)*

**Present:** artefacts produced, approved recommendation, confirmed scope, adopted refactors.

**Ask:** "Design is complete. How do you want to proceed?"
- Implement now, in this session, following the approved plan
- Hand off to `superpowers:writing-plans` — **offered only when superpowers is installed**
- Stop here — artefacts are saved and resumable

**Wait for:** an explicit choice. **Never begin implementing without one.**

## Artefact Formats

Folder layout, both status vocabularies, the `PLANS_INDEX.md` and `INDEX.md` templates, the single-session success path, `session-context.md` contents, and the `user_overrides` entry format are all specified in `artefact-formats.md`, a sibling of this file. **Read it before writing anything in Phase 11**, and when reading prior artefacts in Phase 1.

## `--complete` Flow

No phase agents run. **Draft, present, confirm, then write — never write before confirming.**

1. Locate `<artefact-dir>/<feature-slug>/`. If not found, list available slugs from `PLANS_INDEX.md` and stop.
2. Read every file in the folder.
3. **Draft** `completed-summary.md` — what was built, decisions made, deviations from the plan, and any sub-tasks or deferred refactors left unfinished.
4. **Present the draft and wait for confirmation.**
5. On confirmation: write `completed-summary.md`, set status in `PLANS_INDEX.md` to `complete`, update `INDEX.md`.

Confirmation always precedes both writes.

## Orphaned State Recovery

**Detect in Phase 1** when a feature folder exists with no `PLANS_INDEX.md` entry, or contains `pseudocode.md` but no `INDEX.md` — the signature of a session abandoned between Phase 4b and Phase 11.

Surface at HIL-1: "Found an incomplete plan for `[slug]` from a previous session. A pseudo-code plan already exists. Resume from it, or start fresh?"

- **Resume:** read the existing `pseudocode.md`, reconstruct the `INDEX.md` entry, and continue from **Phase 2b** — not Phase 2a. Phases 4a, 3, and 4b are **not** re-run; the plan already exists and must not be regenerated. Offer plan regeneration only if the user asks for it.
- **Start fresh:** archive to `<slug>-abandoned-<n>/` and begin from Phase 2a.
