---
name: spyglass
description: Use when implementing any Python feature, function, class, or module, before writing implementation code
---

# Spyglass

Structured design analysis before any Python implementation. It prevents reimplementing functionality that already exists, ignoring codebase conventions, writing oversized functions and classes, never considering refactoring, and starting tasks too large for one session. Twelve phases, ten human-in-the-loop checkpoints, and a set of persistent artefacts that make a design resumable across sessions. Three further flows work on code that already exists: `--verify` checks it against its plan, `--audit` assesses it without a plan, and `--complete` closes a feature out.

**Announce at start, verbatim:**

> I'm using the spyglass skill to design this before writing code.

**Terminal state.** This skill produces design artefacts and stops at Phase 12. It does not implement. Implementation happens only after an explicit choice at HIL-10 — never on the skill's own initiative, and never as an inferred continuation.

**Invocation keywords** — recognised in the invocation text, not CLI flags:

| Keyword | Effect |
|---|---|
| `--tests` | Force test planning (Phase 10) |
| `--refactor` | Force refactor assessment even when no signal fires |
| `--no-refactor` | Suppress it even when signals fire (complexity is still measured) |
| `--complete <slug>` | Mark a feature complete and write its summary |
| `--verify <slug>` | Check implemented code against the plan it came from |
| `--auto` | Run to completion, taking the default at every checkpoint that has one |
| `--audit <path>` | Assess existing code and return a prioritised backlog, with no task |

Scope: Python projects only.

## Speaking to the User

Everything in this document below this section — phase numbers, HIL numbers, Levels, slugs, signals, fast-path variants — is **internal vocabulary for running the process**. None of it belongs in a message to the user. They did not read this file and have no idea what "HIL-2" or "Level 1" means.

**Rules for every user-facing message:**

1. **No internal names.** Never write `HIL-3`, `Phase 4b`, `Level 1`, `fast-path-add`, `S2`, `slug`, or `artefact` to the user. Say *checkpoint*, *the plan*, *the structure*, *a name for this work*, *notes*.
2. **Do not quote their own request back to them.** They know what they asked for. Never justify a decision by restating their words or citing a rule they cannot see — not "the task is under 15 words and describes a single new function", just "this looks small".
3. **Do not explain the machinery.** Which phases run, why a rule fired, how a path resolved — all irrelevant unless something they need to act on depends on it. Report the outcome, not the derivation. **This includes narrating your own transitions**: "moving to the complexity check", "S1 fired", "now running the style review". Do the thing and report what it found.
4. **Do not pre-empt worries they do not have.** Volunteering that a file was *not* modified plants the idea that it might have been.
5. **Ask for what you need, not for validation of what you did.** A checkpoint is a question with a decision behind it.
6. **Short.** A checkpoint is a handful of lines. If it needs a heading and five bullets, it is over-explaining.

**This is the shape to aim for:**

<Bad>
Fast-path: fast-path-add — the task is under 15 words and describes a single new function ("a function that converts a timestamp string to ISO-8601"), not a modification to a named existing symbol. This skips Phases 3, 8, 10 (and their HILs), runs a reduced Phase 5, and still requires HIL-2 on the Level 1 summary alone.

HIL-1 — Slug, prior context, scope signal
- Generated slug: convert-timestamp-iso8601
- Artefact directory: /Users/…/.claude/spyglass/ — resolved to the repo root rather than the subfolder because .git was found there and takes precedence per the artefact-resolution rule
- Lightweight scope signal: trivial/small
</Bad>

<Good>
This looks small, so I'll keep the design pass light — I'll check what already exists, then sketch the function before writing it.

I'm calling this work **convert-timestamp-iso8601**. Nothing related from previous sessions. Notes go in `.claude/spyglass/`.

Does that name work, and does "small" match what you expected?
</Good>

The good version carries every decision the user can actually act on, and none of the reasoning that produced them. When a user needs the reasoning, they will ask.

**One exception:** if a resolution genuinely surprises the user's expectation — the project root landed somewhere they would not predict, or no project was found at all — say so in one plain sentence, because they may need to move and re-run. State the fact, not the rule that produced it.

## Dispatching Agents

Every agent this document names — `spyglass:codebase-searcher`, `spyglass:complexity-assessor`, and the rest — is a real agent definition with its own file, its own rules, and its own fallback behaviour, none of which live in this document. **Dispatching one means calling the Agent tool with `subagent_type` set to its exact namespaced name.** A behavioural run has been observed writing a prompt that reconstructed `complexity-assessor`'s rules from memory — the tool flags, the fallback order, the threshold — and sending it to `subagent_type: general-purpose` instead, for `complexity-assessor`, `style-checker`, and `refactor-assessor` in a single run. Nothing announced this. The output was detailed enough to look correct, and it was missing every guardrail this document does not happen to restate: never reconciling two measuring tools against each other, never prompting to install one, the exact interpretation of a borderline score.

**Every "Receives" line below names the agent to dispatch. That name is the literal `subagent_type` value** — `spyglass:complexity-assessor`, not "a complexity assessment", and never `general-purpose` carrying a hand-written imitation of one. If a real agent exists for the work, use it; do not reason that you already know what it would say.

## Artefact Directory Resolution

**Nearest marker wins.** Walk upward from the working directory and stop at the **first** directory containing a Python project marker — `pyproject.toml`, `setup.py`, `setup.cfg`, or `requirements.txt`. Only if none is found anywhere above, fall back to the nearest `.git`.

Do **not** prefer `.git` over a nearer Python marker. A Python project nested inside a larger repository — a fixture, an example, a package in a monorepo — is the project the user is working in. Resolving past it to the outer repository points every subsequent phase at the wrong codebase: the reuse search reads unrelated files, and the artefacts land outside the project they describe.

1. Nearest Python marker found → artefact directory is `<that-directory>/.claude/spyglass/`.
2. No Python marker, but a `.git` above → artefact directory is `<git-root>/.claude/spyglass/`.
3. Neither → artefact directory is `~/.claude/spyglass/`. Say plainly that no project was found.
4. **Decide whether the directory existed before this run touched anything, and decide it in Phase 1** — before writing a single artefact. If it did not, create it and write `.gitignore` containing one line, `*`, *first*, before any other file goes in.

**Order matters here, and getting it wrong is silent.** Writing an artefact creates the parent directory as a side effect. Check "does it exist?" after that, and the answer is yes — so the guard below fires, the `.gitignore` is never written, and every design note sits visible in the user's `git status`. That has happened. The promise that this tree is invisible to git is one of the few things this plugin guarantees outright, and it fails without any error.

A `.gitignore` whose pattern matches everything, including itself, makes the whole tree invisible to git with **zero modification of any file the user owns**. Mention the location once, on the run that creates it, in one short line — for example:

> Design notes for this will go in `.claude/spyglass/`, kept out of git.

Do not explain the self-ignoring mechanism, and do not volunteer that their `.gitignore` was left alone. Nobody asked, and raising it invites a worry that did not exist.

**Hard rules:**

- **Never read, create, or modify the project's root `.gitignore`.** It is tracked, shared, often governed by team policy, and in a monorepo the wrong one is easy to pick. Spyglass ships to strangers; it leaves their files alone.
- **Do not recreate `.claude/spyglass/.gitignore` if the directory already existed when this run started.** A user who deleted it wants these artefacts committed. This applies only to a directory left by an *earlier session* — never to one this run created moments ago by writing a file into it.
- The self-ignoring `.gitignore` is still written under the `~/.claude/spyglass/` fallback, since `~/.claude/` is occasionally kept under version control.

## Project Configuration

Some answers do not change between features. The docstring convention is the same on Tuesday as it was on Monday; so is the complexity budget and the list of directories nobody wants touched. Asking every run turns a settled matter into a recurring interruption, and interruptions that carry no decision are how the ones that matter get waved through.

**Read once, in Phase 1.** Look for `[tool.spyglass]` in the `pyproject.toml` that resolved the artefact directory. If there is no `pyproject.toml`, look for `.spyglass.toml` beside it. Absent either, everything below falls back to its default and nothing is mentioned.

```toml
[tool.spyglass]
docstring_style   = "google"      # google | numpy | sphinx — settles Phase 3
complexity_budget = 15            # cognitive complexity target for new functions
max_function_lines = 40           # Phase 7's hard (blocking) limit
max_class_lines   = 200           # Phase 7's hard (blocking) limit, and signal S3's threshold
auto              = false         # run unattended by default
exclude           = ["migrations/**", "vendor/**"]
```

Every key is optional. An unrecognised key is ignored in silence — a config written against a later version must not break an earlier one.

**What it settles:**

| Key | Effect |
|---|---|
| `docstring_style` | Phase 3 reports it as established rather than inferring, and never raises **S4** for docstrings. A project that has decided does not have an inconsistency, it has a migration |
| `complexity_budget` | The default budget Phase 4b records, and the threshold Phase 8 measures against |
| `max_function_lines`, `max_class_lines` | Phase 7's limits, and S3's threshold |
| `auto` | `--auto` behaviour without typing it. `--no-auto` in the invocation overrides it |
| `exclude` | Paths the searchers, pattern analysis and audit skip entirely |

**Precedence, highest first:**

1. What the user says in this session — always
2. `[tool.spyglass]` / `.spyglass.toml`
3. What Phase 3 infers from the code
4. The defaults above

**Never write this file.** It is the user's, it is tracked, and a plugin that edits a project's config produces an unexpected diff in someone's next commit — the same reason the root `.gitignore` is left alone. If a session establishes something worth making permanent, say so in one line at Phase 12 and let them add it:

> You've now told me twice that this project uses NumPy docstrings. Worth putting `docstring_style = "numpy"` under `[tool.spyglass]` in `pyproject.toml` so I stop asking.

**Mention the config once, on the first run that finds one** — "using the settings in `pyproject.toml`" — and never again. Do not list what it contains; they wrote it.

## Fast-path

Evaluated **before Phase 1**, from the task description alone. Two variants, distinguished by whether the task adds new capability or changes existing behaviour — library investigation only pays off for the former.

**Both fast paths run exactly two checkpoints**, not four. A path that exists to be light must feel light: a change this small does not warrant four stops, and checkpoints that carry no real decision train the user to stop reading the ones that do.

- **Phase 2b and HIL-4 are skipped.** A task that matched a fast path is single-session by definition — asking a scope assessor to confirm that one function fits in one session is a formality with a predetermined answer.
- **HIL-2 is folded into HIL-3.** Present the file-level structure and the contract together in one checkpoint. On a one-function change the structure question is "which file does this go in", which the plan answers anyway.

That leaves: the opening checkpoint (name, prior work, size), then one combined plan checkpoint. Everything else runs without interruption.

**HIL-1b still applies on both fast paths.** It is conditional on genuine ambiguity, not on flow length — and a fifteen-word request is where ambiguity is most likely, not least.

**`fast-path-modify`** — changes existing behaviour, introduces no new capability (add a parameter, fix an off-by-one, rename a symbol, adjust a threshold).
- Criteria: under 15 words AND names an existing function, class, or file AND introduces no new capability
- Skips: Phases 2b, 3, 5, 6, 10 and HIL-2, HIL-4
- Runs: 1, 2a, 4a, 4b, 7, 8, 9 (if signals fire), 11, 12
- Rationale: nothing new is being built, so there is nothing to investigate — but the code being touched may still warrant refactoring, so Phases 8 and 9 stay live

**`fast-path-add`** — adds a small new capability (one function, one small class).
- Criteria: under 15 words AND describes a single new function or small class
- Skips: Phases 2b, 3, 8, 10 and HIL-2, HIL-4
- Runs: 1, 2a, 4a, 4b, **reduced Phase 5**, 6, 7, 9 (if signals fire), 11, 12
- **Reduced Phase 5 dispatches `spyglass:codebase-searcher`, `spyglass:stdlib-searcher`, and `spyglass:deps-searcher`.** Only `spyglass:package-searcher` is skipped.
- Rationale: "write a function that slugifies a string" is short *and* is exactly where reimplementation happens

**Why `deps-searcher` runs even on the fast path.** It does not propose new dependencies — it reports what the project has *already installed*. Those are paid for: no new supply-chain surface, no new licence, nothing added to a lockfile. A project that already depends on a mature date parser should never be handed a hand-rolled format loop because nobody looked. Only `package-searcher`, which proposes genuinely new dependencies, is worth skipping for a task this small.

**Tell the user what it means for them, not which variant fired.** One clause is enough — "this looks small, so I'll keep the design pass light". Never name the variant, list the skipped phases, or explain the criteria that matched; see **Speaking to the User**.

If neither matches, run the standard flow.

## Phase Flow

```
Phase 1  — Context check           [Required]    Locate artefact dir, read index and decisions, detect orphans, generate slug
Phase 2a — Lightweight scope check [Required]    Obvious signal from task description
           └─ HIL-1 (batched): slug + prior context + scope signal
           └─ HIL-1b [Conditional]: clarify an ambiguous request before designing
Phase 4a — Module design (L1)      [Required]    Files, responsibilities, call graph
Phase 3  — Pattern analysis        [Conditional] Targets directories named in L1
           └─ HIL-2 [Required]: confirm L1 summary + patterns (L1 alone if Phase 3 skipped)
Phase 4b — Contract + signature    [Required]    Levels 2-3, constrained by patterns
           └─ HIL-3: approve full plan → saved to pseudocode.md
Phase 2b — Scope re-check          [Standard]    Judge scope against the actual plan (skipped on fast paths)
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

Separate flows, no design phases:
  --complete <slug>   draft summary → confirm → write, mark complete
  --verify <slug>     conformance-checker → HIL-11: plan vs code, decide which is right
  --audit <path>      pattern + complexity + style over real code, refactor-assessor
                      → HIL-12: prioritised backlog, optionally start on one
```

**The numbering is not an error.** Phase numbers label design concerns, not execution positions. Phases 2 and 4 are each split because their halves belong at different points: scope needs a plan to judge (2a/2b), and pattern analysis needs a module design to target but must precede contract design (4a/4b).

**HIL batching:** HIL-1 combines Phase 1 and Phase 2a. HIL-2 combines the Level 1 module-design summary with the pattern report. HIL-7 combines the complexity report with the refactor recommendations it produced. No other checkpoints are batched.

## Phase Specifications

*In execution order.*

### Phase 1 — Context Check — Required

No agent; main instance. Resolve the artefact directory (above), then: (1) read `PLANS_INDEX.md` if present, noting its absence otherwise; (2) identify feature folders semantically related to the current task — reason about relevance rather than matching strings; (3) for each, read `INDEX.md` to surface pending sub-tasks, session context, and deferred refactors; (4) read `[tool.spyglass]` / `.spyglass.toml` if present (see Project Configuration); (5) read `decisions.md` if present — the project's standing conclusions, which shape the reuse investigation later and occasionally answer the task outright; (6) detect orphaned state (see Orphaned State Recovery), surfacing it at HIL-1 if found; (7) generate the slug — lowercase, hyphens for spaces, stop words stripped, max 30 characters. Stop words are the grammatical filler only — articles, prepositions, conjunctions, and auxiliary verbs (`a`, `the`, `to`, `for`, `of`, `in`, `and`, `add`). Nouns that carry meaning are kept, even when the result is well under the cap: "Add CSV export to data pipeline" → `csv-export-data-pipeline`.

→ batched into **HIL-1**

### Phase 2a — Lightweight Scope Check — Required

No agent; main instance, from the task description alone. Emits one signal: `trivial` | `small` | `medium` | `large` | `multi-session-likely`. A signal, not a decision — on the standard flow the binding scope decision is HIL-4, after the plan exists. On a fast path this signal is the only scope judgment made.

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

**Constraints flagged here:** function > `max_function_lines` (40 if unset) lines of logic → redesign; class > `max_class_lines` (200 if unset) lines → split; a contract describing two distinct operations → split candidate.

**Existing-code impact check:** where the plan adds to an existing class or module, estimate resulting size. Exceeding `max_class_lines` (200 if unset), or adding a second distinct responsibility, raises **signal S3**.

**Save:** on HIL-3 approval, write all three stages to `<artefact-dir>/<slug>/pseudocode.md`. This is the working document for the rest of the run.

**Record a complexity budget for each planned function.** In the *Signatures* section, note the cognitive complexity you expect it to land under — 15 unless the function has a stated reason to be denser, in which case say the reason. This costs one number per function and converts an observation into a commitment: Phase 8 measures what already exists, and nothing else in this flow says what the new code is *supposed* to cost. `--verify` checks the built code against these later.

Budgets are targets, not gates. Nothing here blocks on one, and a function that lands over budget for a good reason is a conversation, not a defect.

**Read `conformance-log.md` before finalising the contracts.** Where the same kind of drift has been recorded **three or more times**, raise it once, as an observation rather than a rule — designs that consistently understate their parameters keep doing so until someone notices the pattern. Two occurrences is a coincidence; say nothing.

**Use these exact headings in the file. Do not write "Level 1", "Level 2", or "Level 3" anywhere in it:**

```markdown
# <slug>

## Module design
## Contracts
## Signatures
```

"Level N" names the stage of *writing* the plan, not a section of it. A human opens this file — and the plan is often shown back at a checkpoint, so an internal heading inside it becomes an internal heading on the user's screen. Descriptive names cost nothing and read better to everyone.

→ **HIL-3**

### Phase 2b — Scope Re-check — Standard flow only — `spyglass:scope-assessor`

**Not run on either fast path.** A task that matched a fast path is single-session by definition.

**Receives:** task description + approved `pseudocode.md` (Levels 1–2). **Output:** `scope`; `sub_tasks` (ordered, if multi-session); `current_task`; `rationale`.

**Heuristics against the actual plan:**
- Single-session: ≤ 3 new or modified *implementation* files (tests excluded), ≤ 5 new functions/classes, no schema or public interface changes
- Multi-session: new modules, schema changes, cross-cutting refactors, or > 5 new functions/classes

→ **HIL-4**

### Phase 5 — Library Investigation — Required

**Read `decisions.md` first.** It records what this project has already concluded and why. A prior rejection is a strong prior, not a rule — cite it, say when it was made, and still dispatch the searchers, because a decision that turned on a fact ("not installed", "no release in two years") may no longer hold. What it saves is not the search but the argument: the synthesis starts from what the project already knows instead of re-deriving it.

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

**Receives:** `pseudocode_doc_path`; `standards_path` — the **absolute path** to `python-standards.md`, resolved from this skill's own directory (it is a sibling of this file). Resolve and pass it explicitly: the agent runs with the *user's project* as its working directory, where a relative path to the plugin's own files does not exist, so without an absolute path the rulebook is simply unreadable; and `max_function_lines` / `max_class_lines` — the effective values from Project Configuration (40 / 200 if neither the session nor `[tool.spyglass]` set them). Pass the resolved numbers explicitly rather than letting the agent assume its own defaults, or a project override silently never reaches the check it's meant to change. Checks only what pseudo-code can reveal.

**Hard violations — blocking:** function estimated at > `max_function_lines` lines of logic; class estimated at > `max_class_lines` lines total; `staticmethod` where a module-level function would serve; mutable default arguments in Level 3 signatures.

**Design violations — advisory:** a contract describing two distinct operations (judge the operations, not the word "and"); function name does not clearly describe what it does; public function lacks type annotations; public function lacks a docstring; class does more than one thing.

**Deferred to post-implementation — do not flag here:** imports inside functions; bare `except:` or catching `Exception` without re-raising; `__double_underscore__` misuse. These are invisible in pseudo-code, and flagging them trains the user to rubber-stamp the checkpoint.

Confirms or clears **S3** using the post-HIL-6 state — a hard-violation fix may already have resolved the size problem that raised it.

→ **HIL-6**

### Phase 8 — Complexity Assessment — Conditional — `spyglass:complexity-assessor`

**Trigger:** the task modifies existing Python files rather than being purely net-new. **`--no-refactor` does not suppress this phase** — it suppresses Phase 9. Knowing your change lands in a dense function is useful even when you have already decided not to restructure it, and it is the one moment someone is looking at that function anyway.

**Receives:** the list of existing Python file **paths** the task will modify, and `module_design` so the agent knows which functions sit in the change path. Pass paths, not file contents — the agent has `Read` and fetches what it needs itself.

**Always dispatch `spyglass:complexity-assessor`. This phase is the agent.** Never assess complexity yourself — not when the file is short, not when you have already read it, not when no measuring tool is installed, and not when `--no-refactor` means nothing will be proposed anyway. Reading the file to count branches yourself spends main-instance context on exactly what the delegation exists to keep out of it, and the answer arrives with no tool behind it.

**Measure with a tool, interpret with an agent — the agent owns both.** It has `Bash`: it runs `complexipy --plain --max-complexity-allowed 15 <file>` or `radon cc <file> -s` for each file itself, taking the first tool that is installed and never reconciling two. The main instance does not run radon and does not pipe radon output or file contents through its own context. If radon is absent, **the agent** falls back to reading the files and assessing by eye, noting that the figures are estimates and that radon would improve accuracy — **never prompt to install**, environment setup is not this plugin's business. That fallback belongs to the agent and is not an option for the main instance: "estimate it by eye" describes what happens *inside* the dispatch, never instead of it. The agent then adds what radon does not measure: nesting depth, and which functions the change actually touches.

**Output:** per-function complexity for touched functions, and which tool measured it. Cognitive complexity above 15 (complexipy) or grade C or worse (radon, complexity > 10) raises **S1** — one threshold per tool.

No HIL of its own. If S1 fires, the report is evidence at HIL-7. If nothing fires, it folds into the Phase 12 summary.

### Phase 9 — Refactor Assessment — Conditional — `spyglass:refactor-assessor`

**Trigger:** any of S1–S4 fired, or `--refactor`. Suppressed by `--no-refactor` — **this phase only**; Phase 8 still measures, and its finding folds into the Phase 12 summary instead of into a recommendation. Not user-initiated in normal use.

**Do not announce that you are moving between phases.** A signal firing is not an event the user is waiting to hear about; the finding is. Three separate behavioural runs opened this phase with a line like *"S1 fired: `load_records` already scores 28…"* — twice after the rule against naming signals had already been tightened, because each fix added another prohibition and none supplied the sentence to use instead.

So here is the sentence. When a signal fires and you are about to assess refactoring, say what was found and stop:

> Your change touches `load_records`, which is already dense — complexipy scores it 28 against a threshold of 15. Worth deciding whether to tidy that up.

No identifier, no phase name, no "this triggers". The user learns what is true about their code and what decision is coming. Everything else is bookkeeping they did not ask to see.

**Receives:** fired signals with evidence, `pseudocode.md`, complexity report (if run), pattern report (if run), and the effective `complexity_budget` / `max_class_lines` from Project Configuration so its evidence cites the project's actual thresholds rather than assumed defaults. When S1 fired and complexipy measured it, the complexity report carries **deterministic refactor plans** — line ranges, rules and estimated complexity reductions produced by the tool. Treat those as measured evidence to reason from, not as the recommendation: the analyser knows nothing about what the change is for, or which of its suggestions conflict. **Scope cap:** maximum 5 recommendations, restricted to files the task already touches. If more candidates exist, report the count dropped rather than silently truncating.

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

No agent; main instance. Content is confirmed at HIL-9 **before any write**.

**Also append to `decisions.md`** any decision from this run whose reasoning outlives the feature — a dependency rejected and why, a structural constraint discovered, a convention settled. Feature-scoped decisions stay in `session-context.md`. Include the proposed rows in what HIL-9 confirms; this file is project-wide and never rewritten, so a bad row is permanent.

Read `artefact-formats.md` before writing anything — it carries the status vocabularies, templates, and file contents.

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
| **S1 — Complexity in the change path** | Phase 8 | A function being modified exceeds the threshold of whichever tool measured it — cognitive complexity above 15 (complexipy), or grade C or worse (radon, cyclomatic above 10) |
| **S2 — Near-duplicate existing code** | Phase 6 | The synthesiser recommends `partial-use` against **priority-1 codebase code** — existing code does most of the job, so unifying may beat building alongside it |
| **S3 — Plan pushes existing code over a limit** | Phase 4b + Phase 7 | The plan would take an existing class past `max_class_lines` (200 if unset), or give a module a second distinct responsibility |
| **S4 — Inconsistent patterns in the target area** | Phase 3 | The pattern analyser reports `inconsistent` for any pattern in the directories being touched — new code cannot follow a convention that does not exist |

**`S1`–`S4` are internal identifiers and never appear in a message to the user — including to report that one did *not* fire.** A signal that stayed quiet is not news; it is the machinery working, and narrating it is the leak that has now happened twice. "S1 doesn't fire — `normalise_date` is simple (grade A)" says nothing the user needs and names two things they have never heard of. Either say what was found — "the function you're touching is straightforward, so nothing to restructure there" — or, far better, say nothing and move on.

**Overrides:** `--refactor` forces Phase 9 without a signal; `--no-refactor` suppresses **Phase 9 only** despite one — Phase 8 still measures.

**When no signal fires and no keyword is given:** Phase 9 does not run, and Phase 8's complexity report folds into the Phase 12 summary — visible, without a checkpoint interrupting for a decision with nothing behind it.

Each fired signal is reported at HIL-7 with its evidence, so the user sees *why* the assessment ran.

## `--auto` — running without stopping

Ten checkpoints is a lot to sit through for a change you have already thought about. `--auto` runs the flow to completion, taking the default at every checkpoint that has one, and presents every decision it made at the end for review.

**Two checkpoints still stop, and are not negotiable:**

| Still stops | Why |
|---|---|
| **HIL-1b** — requirement clarification | It is the one checkpoint that asks what *you* meant. Guessing here is the failure this whole skill exists to prevent, and every later phase compounds it. There is no defensible default for "which of two different things did you want" |
| **HIL-6** — hard style violations | A hard violation is a rule the project's own standards say must not ship. Auto-accepting one silently writes it into the plan |

Everything else takes its default: the generated name, the module structure, the plan as designed, the scope assessment, the reuse recommendation, advisory style findings left unaddressed, refactors **not** adopted, the test plan as derived, and the artefacts as drafted. At HIL-10 it stops without implementing, exactly as a normal run does — `--auto` removes checkpoints, it does not remove the terminal state.

**Default to the conservative option every time.** Where a checkpoint offers to do more work — adopt a refactor, expand scope, add a dependency — the default is not to. An unattended run should not be able to grow the task.

### The decision report

At the end, before Phase 12's handoff, list every decision taken on the user's behalf:

> I made these calls without asking — say the word on any of them and I'll revisit:
>
> - Named it **`csv-export-data-pipeline`**
> - Put the writer in a new `export.py` rather than extending `report.py`
> - Left `python-dateutil` alone; the stdlib covers what the plan needs
> - Did **not** adopt the suggested refactor of `load_records` — noted in future-tasks.md instead
> - Two advisory style points left as-is: `summarise` has no return annotation, `export_rows` is 34 lines

**This report is the point of the feature.** A mode that silently makes ten decisions is worse than ten checkpoints, because the decisions still happened and nobody saw them. Report them in the order they were made, say plainly what was chosen, and keep each to one line.

**Record it in `session-context.md` too**, marked as auto-taken rather than user-confirmed. A later session must be able to tell "the user approved this" from "nobody was asked".

## HIL Checkpoint Specifications

**Each checkpoint waits for user input before proceeding. Checkpoints are not optional. Do not batch, skip, or infer an answer to any checkpoint the user has not given.**

### HIL-1 (batched) — Name, prior work, size *(after Phases 1 and 2a)*

This is the first thing the user ever sees. Follow **Speaking to the User** exactly — it sets the tone for the whole run.

**Present** in one short message, in plain language:
- The name you have chosen for this piece of work, and any existing names it might belong under instead
- Anything relevant found from previous sessions — or nothing, said in three words
- Where notes will be kept, one clause, only on the run that creates the directory
- Whether this looks small or large
- If an unfinished plan from a previous session was found, offer to resume it or start fresh
- Only if the project root resolved somewhere surprising, or no project was found: one plain sentence saying so

**Ask:** whether the name fits, whether any prior work listed is relevant, and whether the size matches what they expected.

**Wait for:** a name confirmation or correction; a decision on prior work; a size confirmation.

**Do not** print the internal slug format, the resolution rule, the phase list, or which fast-path variant fired. Do not quote their request back.

### HIL-1b — Requirement clarification *(conditional — after HIL-1, before Phase 4a)*

Every other checkpoint confirms something **Spyglass** produced. This one is different: it asks what the **user** actually meant. It exists because designing the wrong thing correctly is the most expensive failure available here — every phase after it compounds the error, and no amount of style checking or reuse investigation rescues a design that answers the wrong question.

**Trigger — all three must hold:**

1. The request is genuinely open to more than one reading, and
2. The readings would produce **materially different designs** — different inputs, different behaviour, or "extend what exists" versus "write something new", and
3. You can ground the alternatives in something concrete you have already seen in this codebase.

**Do not ask** when the request is merely underspecified in ways a sensible default settles, when the difference is cosmetic, or when you are simply seeking reassurance. An unnecessary question here costs more than it looks: it teaches the user that checkpoints are noise, and that is how the ones that matter get waved through.

**Ask exactly one question.** This is not a requirements interview. If two things are unclear, ask about the one that changes the design most; the rest will surface at the plan.

**Ground every option in what is actually there.** Vague options produce vague answers.

**If existing code plausibly already does the job, "use it as it is and write nothing" must be one of the options, in those words.** Not "extend it", not "a version that handles more" — those still build something. A set of options that all build something has already answered the only question worth asking, and asked the user to pick a flavour. The user may not need the new code at all, and finding that out for the price of one question is the best outcome this skill can produce.

**Example of the shape** — offered because the codebase was read, not invented:

> There's already a `normalise_date` in `src/dataflow/timeutils.py` that converts loose date strings to ISO-8601. What should the new function take?
>
> - **The same loose date strings** — then `normalise_date` already does this; use it as it is and we're done here
> - **Unix epoch strings** — e.g. `"1700000000"`; genuinely different from what `normalise_date` handles, so this is new code
> - **Something else** — tell me the format

Note which option comes first. Doing nothing is the cheapest outcome available, so it is offered first, not buried under the alternatives that make work.

**Wait for:** an answer. Do not proceed to module design on an assumption.

**Do not ask here what the reuse investigation is about to answer.** If the ambiguity only becomes visible once `codebase-searcher` reports at Phase 5, that belongs at HIL-5 — do not re-open it here, and do not ask the same question twice in one run.

**If the answer means the work is unnecessary** — the user confirms existing code already covers it — say so plainly and stop. Offer to extend the existing function instead. Do not design a duplicate because a design was requested.

### HIL-2 (batched) — Module design and patterns *(after Phases 4a and 3)*

**Present:** which files will be created or modified and what each is for, plus the conventions found in those directories.

**Ask:** whether the structure looks right and whether those conventions are accurate.

**Wait for:** confirmation or correction of both. Structure corrections send Phase 4a back for revision before Phase 4b. Convention corrections are authoritative and become hard constraints on Phase 4b.

**Skipped entirely on both fast paths** — folded into HIL-3, which presents structure and contract together. See **Fast-path**.

**When Phase 3 did not run on the standard flow** — a greenfield directory with no Python files — HIL-2 still happens with the conventions half dropped. Ask only whether the structure looks right. Do not explain that a pattern report exists and is absent; the user has no use for the machinery, only the question.

### HIL-3 — Plan approval *(after Phase 4b)*

**Present** the plan in plain language: for each function or method, what it does, what it expects, what it returns, and how it handles the cases that could go wrong — then the signatures. **Do not label these as "Level 2" and "Level 3", or mention levels at all.** Those are internal names for the stages of writing the plan, not headings for the user. See **Speaking to the User**.

**On a fast path**, open with the file-level structure that HIL-2 would otherwise have covered, then the plan itself — one checkpoint, not two.

**Ask:** whether the plan looks right, and whether anything should change before checking what already exists to build it with.

**Wait for:** explicit approval or change requests. Do not proceed until approved — a wrong plan wastes all downstream agent work. `pseudocode.md` is written **on approval**, not before.

**If you notice a likely overlap with existing code while writing the plan**, you may mention it here — it is useful for the user to learn it early. State it as an observation you are about to check, never as a result: "this looks close to `normalise_date`; I'll confirm when I check what already exists." Do not predict what the reuse search will conclude, and do not let the observation shape the plan before it is confirmed.

### HIL-4 — Final scope and sub-task breakdown *(after Phase 2b)*

**Skipped entirely on both fast paths**, along with Phase 2b itself. See **Fast-path**.

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

**Do not name this checkpoint either.** A behavioural run opened it with *"Now this is the batched refactor checkpoint (HIL-7)."* — announcing its own transition, complete with the internal number, precisely what **Speaking to the User** rule 3 already forbids. Go straight to what was found: "Your change touches `load_records`, which is already dense — complexipy scores it 28 against a threshold of 15." No preamble naming what kind of checkpoint this is.

**Present** in one message:
- **Why this ran** — the reason, in the user's terms, with evidence. Name the finding, never the signal: "your change touches `parse_records`, which is already dense — radon grades it D"; "`utils.normalise_date` already covers about 70% of what this plan would build". Writing "S1:" or "S2:" here is exactly the leak that **Speaking to the User** forbids, and this is the checkpoint where it happens, because this is the only one whose whole subject is an internal signal.
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

**A generic affirmation is not a choice.** "Continue", "yes", "that all looks right", "go ahead", "sounds good" — none of these select among three options, and none of them authorise writing to someone's repository. A behavioural run answered this checkpoint with "Yes, that all looks right. Continue." and the skill wrote two new files and edited a third. That is the single failure this skill's terminal state exists to prevent, and the reply that caused it is the most natural thing a half-attentive user could type.

Treat an ambiguous answer here exactly as an ambiguous answer is treated at HIL-1b — say it does not map to an option, and ask again:

> That doesn't tell me which of the three you want, and the first one writes files. Implement now, hand off, or stop here?

**When in doubt, stop.** Of the three options, only one is irreversible; the other two lose nothing. Defaulting to a stop costs the user a sentence, and defaulting to implementation costs them a diff they did not ask for.

**This is the only checkpoint where guessing writes to their repository**, which makes it the one place a wrong inference cannot be walked back with a follow-up message. Under `--auto`, this checkpoint stops without implementing regardless — that is stated in the `--auto` section and repeated here because it is the rule most worth not getting wrong.

## Artefact Formats

Folder layout, both status vocabularies, the `PLANS_INDEX.md` and `INDEX.md` templates, **the headings `pseudocode.md` must use**, the single-session success path, `session-context.md` contents, and the `user_overrides` entry format are all specified in `artefact-formats.md`, a sibling of this file. **Read it before writing anything in Phase 11**, and when reading prior artefacts in Phase 1.

## `--audit` Flow

**Trigger:** `--audit <path>`. No design phases, no task.

Every other flow needs a task before it is any use, which means Spyglass is worth nothing until you are already about to write something. `--audit` points the assessment agents at code that exists and asks what is wrong with it, producing a backlog rather than a plan.

1. Resolve the artefact directory as usual. Honour `exclude` from the project configuration
2. **Dispatch three agents in one response**, concurrently:
   - `spyglass:pattern-analyzer` over the target path — what conventions hold, and where they break down
   - `spyglass:complexity-assessor` over every Python file under it — pass `audit_mode: true`, because there is no change path here and **everything measured is in scope**
   - `spyglass:style-checker` with `source_mode: true` — reviewing real files rather than a plan
3. Every finding raises its usual signal. Dispatch `spyglass:refactor-assessor` with all of them
4. Write `<artefact-dir>/audits/<yyyy-mm-dd>.md` after **HIL-12** confirms
5. Offer to turn any finding into a design task — `/spyglass:spyglass <the finding>` — which is how an audit becomes work rather than a document

**Order findings by what they cost to live with, not by severity label.** A grade-F function nobody touches matters less than a grade-C one in the middle of everything, and an audit that leads with the worst score rather than the worst problem gets read once.

**An audit is not a to-do list.** Existing code that works is not defective for being unfashionable. Report what is measurably costly — complexity in code that changes often, conventions that genuinely conflict, classes past the size limit — and leave taste alone. The fastest way to make this feature worthless is to return forty findings.

**Cap at 15 findings.** Beyond that, report the count omitted and the worst offenders only. A backlog nobody can finish is a backlog nobody starts.

### HIL-12 — Audit findings *(only in the `--audit` flow)*

**Present:** a one-line summary — files scanned, findings worth acting on — then the findings in cost order. Say plainly when there is nothing worth reporting; a clean audit is a real and useful result.

**Ask:** whether to write the report, and whether to start on any finding now.

**Wait for:** confirmation before writing anything.

## `--verify` Flow

**Trigger:** `--verify <feature-slug>`. No design phases run.

This is the only place the design-first claim is tested. Everything else in this skill produces a plan; this asks whether the plan survived contact with the code. A plan that was approved, ignored during implementation and then filed away is worse than no plan, because it leaves a document that reads like a description of the code and is not one.

1. Locate `<artefact-dir>/<feature-slug>/pseudocode.md`. Not found → list the available features from `PLANS_INDEX.md` and stop
2. Dispatch **`spyglass:conformance-checker`** with the absolute plan path and any complexity budgets the plan recorded
3. Present its findings → **HIL-11**
4. On the user's decision, update `session-context.md` with what was accepted and why. Never edit their code
5. **Append each finding to `conformance-log.md`** with how it was resolved. One drift is noise; the same drift four times is a fact about how this project designs, and Phase 4b reads it back

**Drift is information, not a verdict.** Implementation legitimately discovers what design could not — an edge case needing another parameter, a return type that was wrong on paper. The useful question is *which* to correct: the plan or the code. Ask it that way. A run that reports drift as failure teaches people to stop running it.

**`--verify` never edits code and never silently rewrites the plan.** Updating the plan to match reality is a valid outcome and requires the user to say so at HIL-11.

### HIL-11 — Conformance findings *(only in the `--verify` flow)*

**Present:** what matches, what drifted, what is missing, in that order — the summary first, so a clean result takes one line and does not read like a report of problems.

**Ask:** for each drift, whether the code is right (update the plan) or the plan is right (leave it flagged for them to fix). Offer "accept all as-is" when everything looks deliberate; that is the common case and should cost one keystroke.

**Wait for:** a decision per drift, or a blanket one. Then write `session-context.md`.

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
