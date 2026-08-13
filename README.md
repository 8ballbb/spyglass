![Spyglass](assets/spyglass.png)

# Spyglass

Design-first Python development for Claude Code.

> Named for the instrument you raise before you cross unfamiliar ground. It doesn't move you an inch — it just means you know what's out there before you commit.

## What it does

Spyglass runs structured design analysis before you write a line of Python, so the common failure modes never make it into the code:

| Failure mode | How Spyglass addresses it |
|---|---|
| Reimplementing existing functionality | Four parallel library-investigation agents (codebase, stdlib, dependencies, PyPI) plus a synthesiser |
| Ignoring codebase conventions | A pattern-analysis pass runs before contract design and constrains it |
| Oversized functions / classes | Style checking enforces Google style guide rules on the plan, not just the code |
| Refactoring never considered | Four detection signals auto-trigger a refactor assessment; adopted refactors get written into the plan |
| Tasks too large for one session | A two-phase scope assessment plus persistent, resumable artefacts |
| No cross-session continuity | The artefact folder is read at the start of every run and updated at the end |
| Too many assumptions, too little input | A human-in-the-loop checkpoint at every major decision point |

Spyglass produces a design and stops. It never implements on your behalf — implementation is always a separate, explicitly-chosen step at the end of the run.

## Installation

```
/plugin marketplace add 8ballbb/spyglass
/plugin install spyglass
```

## Usage

```
/spyglass <task description>              standard run
/spyglass --tests <task description>       force test planning
/spyglass --refactor <task description>    force refactor assessment even when no signal fires
/spyglass --no-refactor <task description> suppress refactor assessment even when signals fire
/spyglass --complete <feature-slug>        mark a feature complete and write its summary
```

Refactor assessment is **signal-driven by default** — Spyglass watches for four warning signs (complexity, near-duplicate code, plans that push existing files over a size limit, inconsistent conventions) and runs the assessment on its own when one fires. Neither `--refactor` nor `--no-refactor` is needed for normal use; they only override that judgment in either direction.

## What a run looks like

**It is interactive.** A full run has twelve phases and ten checkpoints where Spyglass stops and waits for your input — it does not run to completion unattended. Two fast paths skip most of this for small changes.

```
Phase 1  — Context check                          Locate artefacts, detect orphaned state, generate slug
Phase 2a — Lightweight scope check                 └─ HIL-1: slug + prior context + scope signal
Phase 4a — Module design (Level 1)
Phase 3  — Pattern analysis (conditional)          └─ HIL-2: module structure + conventions found
Phase 4b — Contract + signature design              └─ HIL-3: approve the full plan
Phase 2b — Scope re-check                           └─ HIL-4: confirm scope + sub-task breakdown
Phase 5  — Library investigation (4 agents, parallel)
Phase 6  — Investigation synthesis                  └─ HIL-5: approve reuse recommendation
                                                     └─ HIL-5b (conditional): approve revised plan
Phase 7  — Style & principles review                └─ HIL-6: fix hard violations, pick design ones
Phase 8  — Complexity assessment (conditional)
Phase 9  — Refactor assessment (conditional)        └─ HIL-7: complexity + refactor recommendations
Phase 10 — Test planning (conditional)               └─ HIL-8: confirm test cases
Phase 11 — Artefact update                          └─ HIL-9: confirm content before it's written
Phase 12 — Handoff                                  └─ HIL-10: implement now / hand off / stop here
```

Cost is proportional to how much of that flow actually runs — most runs use far fewer than eleven agents:

| Path | Agents spawned | Which |
|---|---|---|
| `fast-path-modify` (changing existing behaviour) | 3–4 | scope-assessor, style-checker, complexity-assessor, + refactor-assessor if a signal fires |
| `fast-path-add` (one small new function or class) | 5–6 | scope-assessor, codebase-searcher, stdlib-searcher, synthesiser, style-checker, + refactor-assessor if a signal fires |
| Standard, no conditionals, no signals | 7 | scope-assessor, all 4 library-investigation searchers, synthesiser, style-checker |
| Standard + pattern analysis + complexity | 9 | the above + pattern-analyzer, complexity-assessor |
| Everything, including refactor and test planning | 11 | all agents |

The two fast paths are chosen automatically from the task description — a short description that clearly names an existing function to modify, or clearly describes one small new function, skips library investigation and other phases that wouldn't pay off. Anything else runs the standard flow.

## Where artefacts go

Every design artefact — pseudo-code plans, session context, test plans, index files — is written to `.claude/spyglass/` inside your project. On first run, Spyglass writes `.claude/spyglass/.gitignore` containing a single line, `*`, which makes that entire directory invisible to git.

**Your project's root `.gitignore` is never read, created, or modified.** This is deliberate: that file is tracked, shared, and often governed by team policy, and a plugin that silently edits it produces an unexpected diff in your next commit. Spyglass leaves it alone, always. If you'd rather have the artefacts tracked, delete `.claude/spyglass/.gitignore` — Spyglass will not recreate it.

## Requirements

- A Python project.
- [`radon`](https://pypi.org/project/radon/) is optional. If it's installed, it improves the accuracy of complexity assessment; if it isn't, Spyglass proceeds without it and never prompts you to install it — your environment is not this plugin's business.
- No dependency on any other plugin. Every phase runs standalone; if `superpowers` happens to be installed, Spyglass offers an additional handoff option at the end, but nothing about the design flow requires it.

## Licence

MIT — see [LICENSE](LICENSE).
