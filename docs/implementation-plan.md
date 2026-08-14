# Spyglass Plugin Implementation Plan

> **Status note:** This is the original implementation plan, retained in the repo as a record of how the build was structured and sequenced. The build is complete. Where this document diverges from what actually shipped, `docs/design-spec.md` and the code govern — this file is history, not a source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally verify `spyglass`, a distributable Claude Code plugin whose skill runs a 12-phase design analysis over a Python task before any code is written.

**Architecture:** A plugin directory containing one skill (`SKILL.md` + `python-standards.md`), eleven agent definitions, a command wrapper, and two JSON manifests. The skill orchestrates; the agents do bounded single-purpose work and report back. Everything is markdown and JSON — there is no runtime code.

**Tech Stack:** Markdown with YAML frontmatter, JSON manifests, git. Python 3 only for validating JSON and as the fixture project's language. `radon` optionally for one agent, never required.

**Source spec:** now in this repo at [`docs/design-spec.md`](design-spec.md), moved there in Task 11. Cited below as **spec:NNN** for line numbers, which refer to the spec as it stood during the build.

## Global Constraints

- **Repo location:** `~/Desktop/projects/spyglass/`
- **Plugin name:** `spyglass` — used verbatim in `plugin.json`, `marketplace.json`, the skill directory, and the agent namespace
- **Agent naming:** bare names (`codebase-searcher`), never prefixed with `python-` — the plugin namespace is automatic, giving `spyglass:codebase-searcher`
- **Agent frontmatter `tools`:** comma-separated PascalCase (`Read, Grep, Glob`), NOT a YAML array. A YAML array will fail to load
- **Never omit `tools` to mean "no tools."** An omitted `tools` key makes the agent inherit the parent's entire toolset — the opposite of a restriction. `stdlib-searcher`, which needs none, is given the narrowest harmless grant (`tools: Read`) with a frontmatter comment recording why the key must not be deleted, and a body instruction forbidding its use
- **Never write to the user's root `.gitignore`** from skill runtime — artefact self-ignoring uses `.claude/spyglass/.gitignore` containing `*`
- **No hard dependency on superpowers** — the Phase 12 handoff is conditional on its presence
- **No hard dependency on radon** — degrade to agent-only assessment, never prompt to install
- **Licence:** MIT
- **Version:** `0.1.0` in `plugin.json`
- **The naming line**, verbatim, in README beneath the image: *"Named for the instrument you raise before you cross unfamiliar ground. It doesn't move you an inch — it just means you know what's out there before you commit."*
- **British spelling** in prose to match the spec (`synthesiser`, `artefact`, `behaviour`) — but `investigation-synthesiser` is the exact agent filename and must match everywhere
- **No push to any remote** without explicit user confirmation

---

## File Structure

```
~/Desktop/projects/spyglass/
├── .claude-plugin/
│   ├── plugin.json                    # manifest: name, version, licence, keywords
│   └── marketplace.json               # self-hosted marketplace entry
├── commands/
│   └── spyglass.md                    # thin wrapper → clean /spyglass entry point
├── skills/
│   └── spyglass/
│       ├── SKILL.md                   # the 12-phase workflow + 10 HIL checkpoints
│       └── python-standards.md        # distilled Google Style Guide + PEP 8
├── agents/
│   ├── pattern-analyzer.md            # Phase 3  — codebase conventions
│   ├── scope-assessor.md              # Phase 2b — session sizing
│   ├── codebase-searcher.md           # Phase 5  — reuse: own project
│   ├── stdlib-searcher.md             # Phase 5  — reuse: stdlib
│   ├── deps-searcher.md               # Phase 5  — reuse: installed deps
│   ├── package-searcher.md            # Phase 5  — reuse: PyPI
│   ├── investigation-synthesiser.md   # Phase 6  — weighs all four
│   ├── style-checker.md               # Phase 7  — plan-stage violations
│   ├── complexity-assessor.md         # Phase 8  — radon + interpretation
│   ├── refactor-assessor.md           # Phase 9  — signal-driven recommendations
│   └── test-planner.md                # Phase 10 — cases from contracts
├── tests/
│   └── fixtures/sample-project/       # planted conditions for behavioural tests
├── docs/
│   └── design-spec.md                 # the spec, moved in Task 11
├── assets/
│   └── spyglass.png                   # user-supplied, Gemini-generated
├── .gitignore
├── README.md
└── LICENSE
```

**Responsibility split.** `SKILL.md` owns *sequence and interaction* — which phase runs when, what each HIL checkpoint asks, when signals fire. Agent files own *bounded judgment* — one job each, no knowledge of the phase order. `python-standards.md` owns *the rulebook*, consumed by `style-checker` so the rules can be revised without touching agent logic.

**Deviation from spec, flagged:** `tests/fixtures/sample-project/` is not in the spec. It exists because eleven agents that search, measure, and pattern-match cannot be verified against an empty directory. It ships in the repo so contributors can re-run the same checks.

---

## Task Ordering Rationale

Agents come before `SKILL.md` because the skill references them by name — writing it last means every reference points at a file that exists. Agents are created and structurally validated in Tasks 4–8 but **behaviourally** tested once in Task 9, after a single plugin reload, rather than forcing a reload cycle per task.

---

### Task 1: Repository scaffold, manifests, and command wrapper

**Files:**
- Create: `~/Desktop/projects/spyglass/.claude-plugin/plugin.json`
- Create: `~/Desktop/projects/spyglass/.claude-plugin/marketplace.json`
- Create: `~/Desktop/projects/spyglass/commands/spyglass.md`
- Create: `~/Desktop/projects/spyglass/.gitignore`
- Create: `~/Desktop/projects/spyglass/LICENSE`

**Interfaces:**
- Produces: a loadable plugin named `spyglass` registering the `/spyglass` command. Every later task adds files inside this tree.

- [ ] **Step 1: Define the acceptance check and confirm it fails**

Run:
```bash
test -f ~/Desktop/projects/spyglass/.claude-plugin/plugin.json && echo PRESENT || echo ABSENT
```
Expected: `ABSENT`

- [ ] **Step 2: Create the directory tree and initialise git**

```bash
mkdir -p ~/Desktop/projects/spyglass/{.claude-plugin,commands,skills/spyglass,agents,tests/fixtures,docs,assets}
cd ~/Desktop/projects/spyglass
git init
```

- [ ] **Step 3: Write `.claude-plugin/plugin.json`**

Replace `<author>`, `<email>`, `<user>` with the real values before committing — ask the user if unknown.

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

- [ ] **Step 4: Write `.claude-plugin/marketplace.json`**

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

- [ ] **Step 5: Write `commands/spyglass.md`**

```markdown
---
description: Design-first Python development — plan, investigate reuse, and enforce standards before writing code
argument-hint: Task description, optionally with --tests, --refactor, --no-refactor, or --complete <slug>
---

Invoke the `spyglass` skill and follow it exactly. Pass the user's arguments through verbatim, including any of the `--tests`, `--refactor`, `--no-refactor`, or `--complete` keywords.

Do not begin designing or implementing before loading the skill.
```

- [ ] **Step 6: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
venv/
.DS_Store
*.egg-info/
dist/
build/
.pytest_cache/
```

- [ ] **Step 7: Write `LICENSE`**

Standard MIT text, copyright year 2026, holder `<author>`.

- [ ] **Step 8: Verify both manifests are valid JSON**

Run:
```bash
cd ~/Desktop/projects/spyglass
python3 -m json.tool < .claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
python3 -m json.tool < .claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
```
Expected: both print `OK`. A trailing comma or smart quote fails here.

- [ ] **Step 9: Verify no placeholder values survive**

Run:
```bash
grep -rn "<author>\|<email>\|<user>" ~/Desktop/projects/spyglass/.claude-plugin/ ~/Desktop/projects/spyglass/LICENSE
```
Expected: no output. Any hit means a placeholder was left in — resolve with the user before committing.

- [ ] **Step 10: Install locally and confirm the command registers**

Ask the user to run, in a Claude Code session:
```
/plugin marketplace add ~/Desktop/projects/spyglass
/plugin install spyglass
```
Then type `/spyglass` and confirm it appears in the command list with the description from Step 5.

Expected: command present. If it does not appear, the manifest `name` and the directory layout disagree — recheck `.claude-plugin/plugin.json`.

- [ ] **Step 11: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add .claude-plugin commands .gitignore LICENSE
git commit -m "feat: plugin scaffold, manifests, and /spyglass command wrapper"
```

---

### Task 2: Test fixture project

**Files:**
- Create: `tests/fixtures/sample-project/pyproject.toml`
- Create: `tests/fixtures/sample-project/src/dataflow/__init__.py`
- Create: `tests/fixtures/sample-project/src/dataflow/timeutils.py`
- Create: `tests/fixtures/sample-project/src/dataflow/ingest.py`
- Create: `tests/fixtures/sample-project/src/dataflow/report.py`
- Create: `tests/fixtures/sample-project/tests/test_timeutils.py`
- Create: `tests/fixtures/README.md`

**Interfaces:**
- Produces: a Python project with four deliberately planted conditions, each targeting a specific agent:
  - **P1** `timeutils.normalise_date` — near-duplicate of a plausible planned function, so `codebase-searcher` has an `exact`/`partial` match to find and `investigation-synthesiser` can raise **S2**
  - **P2** `ingest.load_records` — cyclomatic complexity above 10, so `complexity-assessor` raises **S1**
  - **P3** mixed Google and NumPy docstring styles across `timeutils.py` and `report.py`, so `pattern-analyzer` reports `inconsistent` and raises **S4**
  - **P4** `pyproject.toml` declares pytest and one dependency, so `deps-searcher` and `test-planner` have real config to read

- [ ] **Step 1: Confirm the fixture is absent**

Run: `test -d ~/Desktop/projects/spyglass/tests/fixtures/sample-project && echo PRESENT || echo ABSENT`
Expected: `ABSENT`

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "dataflow"
version = "0.1.0"
dependencies = ["python-dateutil>=2.8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `src/dataflow/__init__.py`**

```python
"""Sample data pipeline used as a Spyglass test fixture."""

from dataflow.timeutils import normalise_date

__all__ = ["normalise_date"]
```

- [ ] **Step 4: Write `src/dataflow/timeutils.py` — plants P1 and half of P3 (Google style)**

```python
"""Date and time helpers."""

from datetime import datetime, timezone


def normalise_date(value: str, assume_utc: bool = True) -> str:
    """Convert a loose date string into an ISO-8601 timestamp.

    Args:
        value: A date string in one of several accepted formats.
        assume_utc: Treat naive inputs as UTC rather than local time.

    Returns:
        An ISO-8601 formatted timestamp string.

    Raises:
        ValueError: If the value matches none of the accepted formats.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if assume_utc and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    raise ValueError(f"unrecognised date format: {value!r}")
```

- [ ] **Step 5: Write `src/dataflow/ingest.py` — plants P2 (high complexity)**

Complexity is deliberate. Do not simplify it.

```python
"""Record ingestion."""

import csv
from pathlib import Path


def load_records(path: Path, strict: bool = False, skip_blank: bool = True) -> list[dict]:
    """Load records from a CSV file."""
    records = []
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if skip_blank and not any(row.values()):
                continue
            if "id" not in row or not row["id"]:
                if strict:
                    raise ValueError("missing id")
                else:
                    continue
            if "amount" in row and row["amount"]:
                try:
                    row["amount"] = float(row["amount"])
                except ValueError:
                    if strict:
                        raise
                    row["amount"] = 0.0
            else:
                row["amount"] = 0.0
            if "status" in row and row["status"] not in ("open", "closed"):
                if strict:
                    raise ValueError("bad status")
                row["status"] = "open"
            records.append(row)
    return records
```

- [ ] **Step 6: Write `src/dataflow/report.py` — plants the other half of P3 (NumPy style)**

```python
"""Reporting helpers."""


def summarise(records: list[dict]) -> dict:
    """Summarise a list of records.

    Parameters
    ----------
    records : list of dict
        Records to summarise.

    Returns
    -------
    dict
        Totals keyed by status.
    """
    totals: dict[str, float] = {}
    for record in records:
        status = record.get("status", "open")
        totals[status] = totals.get(status, 0.0) + record.get("amount", 0.0)
    return totals
```

- [ ] **Step 7: Write `tests/test_timeutils.py`**

```python
from dataflow.timeutils import normalise_date


def test_normalise_date_iso_passthrough():
    assert normalise_date("2026-01-15").startswith("2026-01-15")
```

- [ ] **Step 8: Write `tests/fixtures/README.md`**

Document each planted condition — P1 through P4, what it is, which agent it exercises, and the warning that "fixing" them breaks the tests. Use the P1–P4 descriptions from the Interfaces block above.

- [ ] **Step 9: Verify the fixture is valid Python and the complexity plant worked**

Run:
```bash
cd ~/Desktop/projects/spyglass/tests/fixtures/sample-project
python3 -m compileall -q src && echo "syntax OK"
python3 -m radon cc src/dataflow/ingest.py -s 2>/dev/null || echo "radon absent — skip"
```
Expected: `syntax OK`. If radon is installed, `load_records` should show grade C or worse. If it grades B, add another branch until it reaches C — P2 is the whole point of the file.

- [ ] **Step 10: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add tests/
git commit -m "test: fixture project with planted conditions for agent verification"
```

---

### Task 3: `python-standards.md` reference

**Files:**
- Create: `skills/spyglass/python-standards.md`

**Interfaces:**
- Consumes: nothing
- Produces: the rulebook `style-checker` cites in Phase 7. Must state, for each rule, whether it is checkable at **plan stage** or only **post-implementation** — Phase 7 depends on that split (spec:632–645).

- [ ] **Step 1: Confirm absent**

Run: `test -f ~/Desktop/projects/spyglass/skills/spyglass/python-standards.md && echo PRESENT || echo ABSENT`
Expected: `ABSENT`

- [ ] **Step 2: Write the file**

Required sections, in order:

**`## Plan-stage hard rules (blocking)`** — exactly the four from spec:632–636:
- Function estimated at > 40 lines of logic
- Class estimated at > 200 lines total
- `staticmethod` where a module-level function would serve
- Mutable default arguments in signatures, e.g. `def f(x: list = [])`

**`## Plan-stage design rules (advisory)`** — the five from spec:638–643. For the two-operations rule, reproduce the spec's discriminating example verbatim: *"validates the input and returns the parsed record" is one responsibility; "writes the record to disk and sends a notification email" is two.* This example is what stops the rule firing on every well-written contract.

**`## Post-implementation only — do not flag at plan stage`** — the three from spec:645, each with a one-line reason it is invisible in pseudo-code:
- Imports inside functions
- Bare `except:` or catching `Exception` without re-raising
- `__double_underscore__` misuse

**`## Reference rules`** — the Google Style Guide and PEP 8 material the agent may need but which is not itself a check: import grouping order (`__future__`, stdlib, third-party, local; lexicographic within group); naming table (modules/functions/variables `lower_with_under`, classes `CapWords`, constants `CAPS_WITH_UNDER`, internal prefixed `_`); type annotation conventions (`X | None` not `Optional[X]`; no annotation on `self`/`cls`); docstring sections (`Args:`, `Returns:`, `Raises:`); 80-character line limit; 4-space indentation.

**`## Precedence`** — one paragraph: a project convention confirmed at HIL-2 beats a default in this file, except where it would breach a plan-stage hard rule.

- [ ] **Step 3: Verify the plan-stage / post-implementation split is unambiguous**

Run:
```bash
cd ~/Desktop/projects/spyglass/skills/spyglass
grep -c "^## " python-standards.md
grep -n "imports inside functions\|Imports inside functions" python-standards.md
```
Expected: 5 sections. The imports rule must appear **only** under the post-implementation heading — if it also appears under hard rules, Phase 7 will produce false positives on every run.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add skills/spyglass/python-standards.md
git commit -m "docs: python standards reference for plan-stage style checking"
```

---

### Task 4: Investigation agents (Phase 5)

**Files:**
- Create: `agents/codebase-searcher.md`
- Create: `agents/stdlib-searcher.md`
- Create: `agents/deps-searcher.md`
- Create: `agents/package-searcher.md`

**Interfaces:**
- Consumes: `task_description`, `module_design`; `codebase-searcher` additionally consumes `prior_file_list` and `patterns` from Phase 3 when it ran
- Produces: four reports consumed by `investigation-synthesiser` in Task 6. Each must report *what gap remains* — the synthesiser's `partial-use` output depends on that field existing in every report.

- [ ] **Step 1: Confirm absent**

Run: `ls ~/Desktop/projects/spyglass/agents/ 2>/dev/null | wc -l`
Expected: `0`

- [ ] **Step 2: Write `agents/codebase-searcher.md`**

```markdown
---
name: codebase-searcher
description: Searches an existing Python project for functions, classes, or utilities that already provide planned functionality, matching by concept rather than identifier
tools: Read, Grep, Glob
model: sonnet
color: blue
---

You search an existing Python codebase for code that already does what the caller is planning to build.

## What you receive

- `task_description` — what the user wants built
- `module_design` — planned files, functions, and classes
- `prior_file_list` — files already read by pattern-analyzer, if it ran
- `patterns` — established codebase conventions, if available

## How to search

Search by **concept, not identifier**. A function named `normalise_timestamp` is relevant to a planned `to_iso_date` even though the names share nothing. Reason about what code does.

1. Glob for `**/*.py`, excluding `.venv`, `site-packages`, `node_modules`, `build`, `dist`, `__pycache__`
2. Grep for domain nouns and verbs drawn from the task description — not the planned function names
3. Read every candidate that looks plausible. Read the whole file when it is under 400 lines
4. Skip files in `prior_file_list` unless a grep hit points into one

## Output

For each match:

| Field | Content |
|---|---|
| `match_quality` | `exact` — does the whole job; `partial` — does some of it; `related` — adjacent, worth knowing |
| `path` | Repo-relative path |
| `symbol` | Function or class name |
| `does` | What it actually does, one sentence |
| `gap` | What the planned functionality needs that this does not provide |

Order best-first. `gap` is required on every match, including `exact` ones — write `none` if there genuinely is no gap.

## Fallbacks

- No first-party Python files → report `no existing codebase to search`
- Only vendored or third-party code found → report separately, flagged as not first-party

Never report a match you have not read. Never infer behaviour from a name alone.
```

- [ ] **Step 3: Write `agents/stdlib-searcher.md`**

Note the `tools: Read` frontmatter key: this agent uses nothing, but the key cannot be omitted — an omitted `tools` key makes the agent inherit the parent's entire toolset. `Read` is the narrowest harmless grant, kept with a comment forbidding its deletion.

```markdown
---
name: stdlib-searcher
description: Identifies Python standard library modules and functions that already provide planned functionality, reasoning from knowledge without reading files
# `tools` is deliberately narrowed to a single read-only tool. DO NOT DELETE THIS
# KEY. This agent needs no tools at all, but the agent frontmatter schema has no
# way to express an empty tool set — omitting `tools` makes the agent INHERIT THE
# PARENT'S ENTIRE TOOLSET, the exact opposite of what is wanted here. `Read` is
# the narrowest harmless grant available; the body below forbids using it.
tools: Read
model: sonnet
color: green
---

You identify standard library functionality that would make planned code unnecessary.

You work from knowledge alone. **Do not use any tool.** You do not read files, run commands, or search the web. You reason from what you know about the Python standard library. The single read-only tool in your frontmatter exists only because the schema cannot express "no tools" — it is not an invitation to use it.

## What you receive

- `task_description` and `module_design` — what the caller plans to build

## Modules to consider first

`itertools`, `functools`, `collections`, `pathlib`, `contextlib`, `dataclasses`, `typing`, `abc`, `enum`, `datetime`, `io`, `os`, `re`, `json`, `csv`, `logging`, `threading`, `concurrent.futures`, `unittest.mock`

This list is a starting point, not a boundary. Name any stdlib module that fits.

## Output

For each relevant module:

| Field | Content |
|---|---|
| `module` | Module name |
| `symbol` | The specific class or function |
| `provides` | What it does, one sentence |
| `gap` | What the planned functionality needs that it does not cover |

## Discipline

State the Python version a symbol requires when it is 3.9 or later — `datetime.UTC` (3.11), `tomllib` (3.11), `itertools.batched` (3.12) are common traps.

Do not invent APIs. If unsure whether a signature is exact, say what the module does and note that the signature should be checked. A confidently wrong stdlib recommendation is worse than none — it produces code that fails at import.

If nothing in the stdlib fits, say so plainly.
```

- [ ] **Step 4: Write `agents/deps-searcher.md`**

```markdown
---
name: deps-searcher
description: Reports which already-installed third-party packages provide planned functionality, reading the real environment rather than only declared dependencies
tools: Read, Glob, Bash
model: sonnet
color: cyan
---

You determine what the project already depends on, and which of those dependencies already solve the caller's problem.

## What you receive

- `task_description` and `module_design`

## How to look

1. Run `pip freeze` for what is **actually installed**. Declaration files miss editable installs and drift from reality
2. Also read whichever exist: `requirements.txt`, `requirements/*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `poetry.lock` — these give declared constraints
3. Reconcile: a package installed but undeclared is worth flagging; so is one declared but absent

## Output

For each relevant package:

| Field | Content |
|---|---|
| `package` | Distribution name |
| `version` | Installed version, or `declared only` |
| `provides` | The specific API surface that fits, named precisely |
| `gap` | What it does not cover |

Also report `declared_not_installed` and `installed_not_declared` when either set is non-empty — both indicate environment drift the caller should know about.

## Fallbacks

- `pip freeze` fails and no dependency file exists → report `no dependency information found`
- `pip freeze` fails but a declaration file exists → use it and state that the list is declared, not verified

Do not recommend a package the project does not already have — that is `package-searcher`'s job. Your entire value is that these dependencies are already paid for.
```

- [ ] **Step 5: Write `agents/package-searcher.md`**

```markdown
---
name: package-searcher
description: Searches PyPI for well-maintained packages that solve the planned problem, applying safety disqualifiers and reporting adoption evidence
tools: WebSearch, WebFetch
model: sonnet
color: purple
---

You find packages on PyPI that the project does not yet have but arguably should.

## What you receive

- `task_description` and `module_design`

## How to search

1. Search for packages addressing the problem. Search the problem, not the planned function name
2. For each candidate, fetch monthly downloads from `https://pypistats.org/api/packages/<name>/recent`. PyPI package pages do not publish download counts — without this call you will invent a number
3. For each candidate, check vulnerabilities by fetching `https://osv.dev/list?ecosystem=PyPI&q=<name>` — a GET-able page listing the known advisories for that package. **Your only network tool is WebFetch, which issues GET requests and cannot send a request body**, so the OSV JSON query API is not available to you. Read the advisory list and its severities from the page you fetch
4. Establish licence and last release date from the PyPI page or the project repository

## Hard disqualifiers — never recommend a package failing any

- No release within 18 months
- Licence other than MIT, Apache 2.0, BSD, or similarly permissive
- An unresolved critical vulnerability in the OSV advisory list

A package failing a disqualifier is not reported as an option. Mention it only if the caller would otherwise obviously reach for it, and state which disqualifier it failed.

## Reporting floor

Do not surface a package below **≥ 500 GitHub stars OR ≥ 10k monthly downloads**. Below that the typosquat and abandoned-toy risk outweighs the value.

## Adoption is evidence, not a gate

Report stars, monthly downloads, last release date, and maintainer count. Let the synthesiser and the user weigh them. Do not apply an AND-gate across stars and downloads — that rejects well-maintained narrow-purpose packages that are frequently the right answer.

## Output

| Field | Content |
|---|---|
| `package` | Name on PyPI |
| `provides` | What it does |
| `gap` | What it does not cover |
| `licence` | Exact licence |
| `last_release` | Date |
| `downloads_monthly` | From pypistats, or `unavailable` |
| `stars` | From the repository, or `unknown` |
| `cve_status` | `clean`, the specific finding, or `unverified` if the advisory page could not be read |

## Fallback

No network access → report `PyPI search unavailable`. Do not guess at package names or statistics from memory; an unverified recommendation here becomes a dependency in someone's project.
```

- [ ] **Step 6: Verify frontmatter parses on all four**

Run:
```bash
cd ~/Desktop/projects/spyglass/agents
for f in codebase-searcher stdlib-searcher deps-searcher package-searcher; do
  python3 -c "
import sys, yaml
text = open('$f.md').read()
assert text.startswith('---'), '$f: missing opening ---'
fm = text.split('---')[1]
data = yaml.safe_load(fm)
assert 'name' in data and 'description' in data, '$f: missing required key'
assert data['name'] == '$f', '$f: name mismatch'
if 'tools' in data:
    assert isinstance(data['tools'], str), '$f: tools must be a comma string, not a list'
print('$f OK')
"
done
```
Expected: four `OK` lines. A YAML list in `tools` fails here — that is the error this check exists to catch.

- [ ] **Step 7: Confirm `stdlib-searcher` still declares `tools: Read`**

Run: `grep -c "^tools: Read$" ~/Desktop/projects/spyglass/agents/stdlib-searcher.md`
Expected: `1`

Do **not** remove the `tools:` key to achieve "no tools" — an omitted `tools` key makes the agent inherit the parent's entire toolset, which is the opposite of the restriction intended here.

- [ ] **Step 8: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add agents/codebase-searcher.md agents/stdlib-searcher.md agents/deps-searcher.md agents/package-searcher.md
git commit -m "feat: four Phase 5 library investigation agents"
```

---

### Task 5: Planning agents (Phases 3 and 2b)

**Files:**
- Create: `agents/pattern-analyzer.md`
- Create: `agents/scope-assessor.md`

**Interfaces:**
- Consumes: `pattern-analyzer` takes `module_design` (Level 1) and reads its directories; `scope-assessor` takes the approved `pseudocode.md` path
- Produces: `pattern-analyzer` emits a pattern report with per-pattern confidence — an `inconsistent` value raises **S4**. `scope-assessor` emits `scope`, `sub_tasks`, `current_task`, `rationale`.

- [ ] **Step 1: Write `agents/pattern-analyzer.md`**

```markdown
---
name: pattern-analyzer
description: Reads existing Python files in the directories a plan will touch and reports the conventions actually in use, with a confidence level per convention
tools: Read, Grep, Glob, Bash
model: sonnet
color: yellow
---

You report the coding conventions actually in use in the directories a plan is about to modify, so new code matches them.

## What you receive

- `module_design` — the Level 1 design, naming the directories and planned filenames

Your targets come from `module_design`. Do not guess at which directories matter.

## File selection — read at most 10

In priority order:

1. `__init__.py` in each target package
2. Files whose names most resemble the planned filenames
3. Most recently modified — `git log --name-only -n 20` inside a repo, `ls -t` outside one
4. Remaining files up to the cap

Stop at 10. Report how many you read and how many you skipped.

## What to report

- **Import style** — absolute vs. relative, aliasing habits, grouping order
- **Naming** — anything beyond PEP 8 defaults
- **Class vs. module-level functions** — which the codebase reaches for
- **Error handling** — context managers, custom exception hierarchies, which built-ins are raised
- **Docstring format** — Google, NumPy, or Sphinx. Name which
- **Project-specific conventions** — anything a style guide would not predict

## Confidence — required on every pattern

| Level | Meaning |
|---|---|
| `established` | Seen in 3 or more files |
| `observed` | Seen in 1–2 files |
| `inconsistent` | Contradictory usage found — report **both** variants and where each appears |

`inconsistent` is a finding, not a failure. It means new code cannot follow a convention that does not exist, and the caller needs to know before writing any.

## Discipline

Report what is there, not what should be there. If the codebase uses a convention you consider poor, report it as `established` anyway — judging it is someone else's job.

Never report a pattern from a file you did not read.
```

- [ ] **Step 2: Write `agents/scope-assessor.md`**

```markdown
---
name: scope-assessor
description: Judges whether an approved design plan is achievable in one working session and, when it is not, breaks it into ordered sub-tasks
tools: Read
model: sonnet
color: orange
---

You decide whether a design plan is one session of work or several, judging the plan itself rather than the task description.

## What you receive

- `task_description`
- `pseudocode_doc_path` — read Levels 1 and 2 from this file

Read the plan before judging. The task description alone is not sufficient — that estimate was already made and this one supersedes it.

## Heuristics

**Single-session** — all of:
- ≤ 3 new or modified **implementation** files. Test files do not count toward this
- ≤ 5 new functions or classes
- No schema changes and no public interface changes

**Multi-session** — any of:
- A new module
- Schema changes
- Cross-cutting refactors
- More than 5 new functions or classes

## Output

| Field | Content |
|---|---|
| `scope` | `single-session` or `multi-session` |
| `sub_tasks` | Ordered list, each with a name and one-line description. Omit when single-session |
| `current_task` | Which sub-task to implement now. Defaults to the first |
| `rationale` | Which heuristic decided it, citing the actual counts from the plan |

## Sub-task ordering

When multi-session, order so each sub-task leaves the codebase working. A sub-task that leaves imports dangling or tests failing is drawn at the wrong boundary. Prefer vertical slices that deliver something testable over horizontal layers that only make sense once all are done.

State counts explicitly in `rationale` — "4 implementation files, 7 new functions" — so the caller can check your arithmetic rather than trust your conclusion.
```

- [ ] **Step 3: Verify frontmatter**

Run the Step 6 loop from Task 4, substituting `pattern-analyzer scope-assessor` for the filename list.
Expected: two `OK` lines.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add agents/pattern-analyzer.md agents/scope-assessor.md
git commit -m "feat: pattern-analyzer and scope-assessor agents"
```

---

### Task 6: Synthesis and style agents (Phases 6 and 7)

**Files:**
- Create: `agents/investigation-synthesiser.md`
- Create: `agents/style-checker.md`

**Interfaces:**
- Consumes: `investigation-synthesiser` takes the four Task 4 reports; `style-checker` takes `pseudocode.md` and `skills/spyglass/python-standards.md`
- Produces: synthesiser emits one of `use-existing` | `partial-use` | `implement-from-scratch`, and raises **S2** when `partial-use` lands on priority-1 code. Style-checker emits two lists — hard (blocking) and design (advisory) — and confirms or clears **S3**.

- [ ] **Step 1: Write `agents/investigation-synthesiser.md`**

```markdown
---
name: investigation-synthesiser
description: Weighs reports from the codebase, stdlib, dependency, and PyPI searchers and returns a single reuse recommendation with justification
tools: Read
model: sonnet
color: red
---

You turn four independent investigation reports into one decision.

## What you receive

Reports from `codebase-searcher`, `stdlib-searcher`, `deps-searcher`, and `package-searcher`. A partial set is normal — under `fast-path-add` only the first two run, and any agent may report no findings. Note explicitly which sources are missing rather than treating absence as a negative finding.

## Priority order

1. **Existing codebase** — no new dependency, already understood by the team
2. **Python stdlib** — zero cost, zero dependency
3. **Already-installed package** — the dependency is already paid for
4. **New PyPI package** — lowest; every new dependency is a permanent obligation

A worse fit higher in this order frequently beats a better fit lower down. Say so when that is your reasoning.

## Output — exactly one recommendation

| Recommendation | When |
|---|---|
| `use-existing` | A source at priority 1–3 covers the requirement fully |
| `partial-use` | The best source covers part of it |
| `implement-from-scratch` | Nothing fits well enough to justify the coupling |

**`partial-use` must specify:**
- Which source, at which priority level, and for exactly what
- What it does not cover, and why
- Where custom code wraps or extends it
- Integration risks
- Why this approach rather than the alternatives considered

**`implement-from-scratch` must justify each rejection individually.** "Nothing suitable" is not a justification — name what was found and why each was rejected.

## Signal S2

When your recommendation is `partial-use` **against priority-1 codebase code**, raise signal **S2** and say so explicitly.

Existing code doing most of the job is the classic case where generalising it beats building a parallel implementation beside it. That is a refactor, and it should be assessed as one rather than assumed. Raising S2 is not a recommendation to refactor — it triggers an assessment.

## Scope change

Flag a scope change when your recommendation would add a file not in the plan, remove a module boundary, or change the planned function count by more than 2.

A same-interface algorithmic change is not a scope change — it revises the Level 2 algorithm description only.
```

- [ ] **Step 2: Write `agents/style-checker.md`**

```markdown
---
name: style-checker
description: Reviews a pseudo-code design document for style and principle violations detectable before implementation, separating blocking violations from advisory ones
tools: Read
model: sonnet
color: red
---

You review a design document — not code — against the project's Python standards.

## What you receive

- `pseudocode_doc_path` — the three-level design document
- The standards reference at `skills/spyglass/python-standards.md`. Read it; it is the rulebook

## Hard violations — blocking

- Function estimated at more than 40 lines of logic
- Class estimated at more than 200 lines total
- `staticmethod` where a module-level function would serve
- Mutable default arguments in a Level 3 signature, e.g. `def f(x: list = [])`

For each, propose the specific fix to the design document.

## Design violations — advisory

- A contract describing two distinct operations. **Judge the operations, not the word "and"** — "validates the input and returns the parsed record" is one responsibility; "writes the record to disk and sends a notification email" is two
- A function name that does not clearly describe what the function does
- A public function without type annotations
- A public function without a docstring
- A class doing more than one thing

## Do not flag these

Imports inside functions; bare `except:` or catching `Exception` without re-raising; `__double_underscore__` misuse.

All three are invisible in pseudo-code. Flagging them here produces noise on every run, and noise trains the reader to stop reading. They are checked after implementation.

## Signal S3

Confirm or clear **S3** — whether the plan pushes an existing class past 200 lines or gives a module a second distinct responsibility. Judge the **current** state of the document: an earlier fix may already have resolved the condition that raised it. Say which.

## Precedence

A project convention confirmed by the user beats a default in the standards file — except where it would breach a hard violation above.

## Output

Two separate lists, hard first. If a list is empty, say so — do not pad it. Every hard violation needs a proposed fix; every design violation needs a one-line reason it matters.
```

- [ ] **Step 3: Verify frontmatter and the false-positive guard**

Run the Task 4 Step 6 loop for `investigation-synthesiser style-checker`, then:
```bash
grep -n "Judge the operations, not the word" ~/Desktop/projects/spyglass/agents/style-checker.md
grep -n "Do not flag these" ~/Desktop/projects/spyglass/agents/style-checker.md
```
Expected: both present. These two passages are what keep Phase 7 from crying wolf on every run.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add agents/investigation-synthesiser.md agents/style-checker.md
git commit -m "feat: investigation-synthesiser and style-checker agents"
```

---

### Task 7: Refactor chain agents (Phases 8 and 9)

**Files:**
- Create: `agents/complexity-assessor.md`
- Create: `agents/refactor-assessor.md`

**Interfaces:**
- Consumes: `complexity-assessor` takes the list of files being modified; `refactor-assessor` takes fired signals with evidence, `pseudocode.md`, and both prior reports
- Produces: complexity report raising **S1** at radon grade C or worse; up to 5 refactor recommendations each carrying `order` and `risk`

- [ ] **Step 1: Write `agents/complexity-assessor.md`**

```markdown
---
name: complexity-assessor
description: Measures cyclomatic complexity of functions being modified using radon where available, and interprets the result for the change at hand
tools: Read, Bash
model: sonnet
color: yellow
---

You report how complex the code being modified already is, before more is added to it.

## What you receive

- The list of existing files the task will modify
- `module_design` — so you know which functions sit in the change path

## Measure first, interpret second

1. Run `radon cc <file> -s` for each file being modified
2. If radon is not installed, fall back to reading the files and assessing by eye. Note in your report that the figures are estimates and that radon would improve accuracy
3. **Never prompt the user to install radon.** Environment setup is not this plugin's business
4. Add what radon does not measure: nesting depth, and which specific functions the current change actually touches

Radon is the measurement. You are the interpretation. Do not restate its output — explain what it means for this change.

## Signal S1

Any function **in the change path** at radon grade C or worse — cyclomatic complexity above 10 — raises **S1**. Report the grade and the number as evidence.

A grade-D function elsewhere in the file is worth mentioning but does not raise S1. The signal is about what the change touches.

## Output

| Field | Content |
|---|---|
| `file` | Path |
| `function` | Name |
| `grade` | Radon grade, or `estimated` with reasoning |
| `complexity` | The number, when measured |
| `in_change_path` | Whether this task touches it |
| `nesting_depth` | Maximum depth |

State plainly whether S1 fired and on which functions.
```

- [ ] **Step 2: Write `agents/refactor-assessor.md`**

```markdown
---
name: refactor-assessor
description: Recommends targeted refactors when a detection signal has fired, restricted to files the current task already touches, each with adoption order and risk
tools: Read, Grep
model: sonnet
color: orange
---

You recommend refactors that are worth doing because a signal fired — not because refactoring is generally virtuous.

## What you receive

- The fired signals with their evidence. One or more of:
  - **S1** — a function in the change path is radon grade C or worse
  - **S2** — existing codebase code does most of the planned job
  - **S3** — the plan pushes an existing class past 200 lines, or gives a module a second responsibility
  - **S4** — patterns in the target directories are inconsistent
- `pseudocode.md`, plus the complexity and pattern reports when those phases ran

Every recommendation must trace to a fired signal. If you cannot name the signal motivating a recommendation, do not make it.

## Hard scope cap

**Maximum 5 recommendations.** Restricted to files the current task already touches — never unrelated files, however tempting.

If more than 5 candidates exist, report the best 5 and state how many were dropped. Silent truncation reads as "that was everything" when it was not.

## Output per recommendation

| Field | Content |
|---|---|
| `file` / `function` | Where |
| `signal` | Which signal motivated it |
| `problem` | What is actually wrong |
| `approach` | Extract function, split class, generalise an existing function to absorb the new case, unify duplicate implementations, or flatten nesting |
| `order` | `before-current-task` or `after-current-task` |
| `risk` | `low` — internal only; `medium` — changes signatures; `high` — changes public API or a module boundary |

## Choosing order

`before-current-task` when the new code would otherwise land on a structure that makes it worse — a class already at its limit, or a function the change would push past grade D.

`after-current-task` when the refactor is worth doing but the new code does not depend on it. When in doubt choose `after` — a refactor that blocks the actual task is a cost, not a benefit.

## Discipline

Recommend the smallest change that resolves the signal. A recommendation that rewrites a module to fix one grade-C function will be declined, and rightly.

Do not recommend cosmetic changes. Do not recommend renaming for taste. Every recommendation must survive the question: what breaks or slows down if we skip this?
```

- [ ] **Step 3: Verify frontmatter and the scope cap**

Run the Task 4 Step 6 loop for `complexity-assessor refactor-assessor`, then:
```bash
grep -n "Maximum 5 recommendations" ~/Desktop/projects/spyglass/agents/refactor-assessor.md
grep -n "Never prompt the user to install radon" ~/Desktop/projects/spyglass/agents/complexity-assessor.md
```
Expected: both present.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add agents/complexity-assessor.md agents/refactor-assessor.md
git commit -m "feat: complexity-assessor and refactor-assessor agents"
```

---

### Task 8: Test planner agent (Phase 10)

**Files:**
- Create: `agents/test-planner.md`

**Interfaces:**
- Consumes: Level 2 contracts from `pseudocode.md`
- Produces: prose test cases per public function, in the detected framework's conventions, written to `test-plan.md` after HIL-8

- [ ] **Step 1: Write `agents/test-planner.md`**

```markdown
---
name: test-planner
description: Derives test cases from a design document's contracts before implementation exists, using the project's already-established test framework and conventions
tools: Read, Glob
model: sonnet
color: green
---

You derive test cases from contracts, before any implementation exists.

## Detect the framework first

Before writing a single case:

1. `pyproject.toml` — look for `[tool.pytest.ini_options]` or unittest configuration
2. `pytest.ini`, `setup.cfg` under `[tool:pytest]`, `tox.ini`
3. Read the existing test directory — are tests functions, or methods on `unittest.TestCase` subclasses?
4. Default to pytest only when genuinely ambiguous

Match what the project already does. A pytest-style plan dropped into a unittest codebase is friction on every file.

## What you receive

- `pseudocode_doc_path` — derive cases from the **Level 2 contracts**: preconditions, postconditions, edge cases

## Cases per public function

- **Happy path** — the contract's normal case
- **Edge cases** — one per edge case the contract names. The contract already enumerated them; do not invent extras
- **Error conditions** — one per exception the contract says is raised, naming the exception and the trigger

## Naming

- pytest: `test_<function>_<scenario>`
- unittest: the same name, as a method on the relevant `TestCase` subclass

## Output — prose, not code

Describe each case: what it sets up, what it calls, what it asserts. Do not write implementations. The design is not built yet, and test code written against an unbuilt interface goes stale the moment the interface shifts.

## Discipline

If a contract's edge case cannot be tested as described, say so. That is a finding about the contract, not a gap in the test plan — an untestable contract is usually an underspecified one.

Do not pad. Three cases that matter beat twelve that restate the same behaviour.
```

- [ ] **Step 2: Verify frontmatter and that all 11 agents now exist**

Run:
```bash
ls ~/Desktop/projects/spyglass/agents/*.md | wc -l
```
Expected: `11`

Run the Task 4 Step 6 loop for `test-planner`.
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add agents/test-planner.md
git commit -m "feat: test-planner agent"
```

---

### Task 9: `SKILL.md` — the workflow

**Files:**
- Create: `skills/spyglass/SKILL.md`

**Interfaces:**
- Consumes: all 11 agents by their namespaced names (`spyglass:codebase-searcher`, etc.); `python-standards.md` via `style-checker`
- Produces: the entire user-facing behaviour. This is the file that makes the plugin work.

**Size target:** under 400 lines. If it grows past that, move the artefact templates (spec:725–746) into a sibling `artefact-formats.md` and reference it. Do **not** externalise the HIL checkpoint specs — an externalised checkpoint is a skipped checkpoint.

- [ ] **Step 1: Confirm absent**

Run: `test -f ~/Desktop/projects/spyglass/skills/spyglass/SKILL.md && echo PRESENT || echo ABSENT`
Expected: `ABSENT`

- [ ] **Step 2: Write the frontmatter**

The description states triggering conditions only — never the workflow. A description that summarises the process causes agents to follow the summary instead of reading the file.

```markdown
---
name: spyglass
description: Use when implementing any Python feature, function, class, or module, before writing implementation code
---
```

- [ ] **Step 3: Write the opening and announcement**

Required content:
- One-paragraph overview: design analysis before implementation, for Python
- **Announce at start:** `"I'm using the spyglass skill to design this before writing code."`
- The terminal-state rule: the skill produces artefacts and stops at Phase 12; implementation only follows an explicit choice at HIL-10

- [ ] **Step 4: Write the artefact directory resolution section**

Reproduce spec:469–473 exactly:
1. Search upward for `.git`, `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`. Prefer the directory containing `.git` when markers appear at multiple levels
2. Found → `<project-root>/.claude/spyglass/`
3. Not found → `~/.claude/spyglass/`, stated plainly
4. If absent, create it and write `.gitignore` containing a single `*`

Include the announcement verbatim: *"Created `.claude/spyglass/` for design artefacts. It's self-ignored from git — your `.gitignore` was not modified."*

State the rule explicitly: **never read, create, or modify the project's root `.gitignore`.** Do not recreate the self-ignore file if the directory already exists — a user who deleted it wants these artefacts committed.

- [ ] **Step 5: Write the fast-path section**

Reproduce spec:304–321. Both variants with their criteria, what each skips, what each runs, and the one-line rationale for each. Include the instruction to announce which variant applies and why.

Critical detail: `fast-path-add` runs a **reduced Phase 5** — `codebase-searcher` and `stdlib-searcher` only.

- [ ] **Step 6: Write the phase flow**

Reproduce the execution-order block at spec:276–302 verbatim as a fenced code block. It is the single most-consulted part of the file.

Follow it with the note explaining why phases 2 and 4 are split (spec:272), so the non-sequential numbering does not read as an error.

- [ ] **Step 7: Write the twelve phase specifications**

One section per phase, in execution order: 1, 2a, 4a, 3, 4b, 2b, 5, 6, 7, 8, 9, 10, 11, 12. Source content from spec:467–776.

For each phase state: whether it is required, conditional, or optional; its trigger if conditional; which agent runs it, by namespaced name; what that agent receives; and which HIL checkpoint follows.

Two details that are easy to lose and expensive to lose:
- **Phase 4a produces Level 1 only**, and is held in context — `pseudocode.md` is not written until HIL-3 approval
- **Phase 5 dispatches all four agents in a single response** so they run concurrently, and Phase 6 blocks until all return

- [ ] **Step 8: Write the refactor signal detection section**

Reproduce the four-signal table (spec:352–357) with each signal's source phase and firing condition. Then the override rules: `--refactor` forces Phase 9 without a signal, `--no-refactor` suppresses it despite one.

State the no-signal behaviour explicitly: Phase 9 does not run, and Phase 8's complexity report folds into the Phase 12 summary rather than raising a checkpoint with nothing behind it.

- [ ] **Step 9: Write the ten HIL checkpoint specifications**

Reproduce spec:367–459. Each checkpoint needs all three parts — what to **present**, what to **ask**, what to **wait for**. A checkpoint missing its wait condition is not a checkpoint.

Open the section with: **"Each checkpoint waits for user input before proceeding. Checkpoints are not optional. Do not batch, skip, or infer an answer to any checkpoint the user has not given."**

Do not omit HIL-5b — it is conditional, and it is what reinstates the HIL-3 approval that a re-plan invalidates.

- [ ] **Step 10: Write the artefact formats section**

The folder layout (spec:213–225), both status vocabularies with their meanings (spec:707–723), the `PLANS_INDEX.md` and `INDEX.md` templates (spec:725–746), the single-session success path (spec:748), `session-context.md` contents (spec:750–754), and the `user_overrides` entry format (spec:756–762).

- [ ] **Step 11: Write the `--complete` and orphan-recovery sections**

`--complete`: the five steps at spec:329–333, with the ordering rule stated plainly — **draft, present, confirm, then write.** Never write before confirming.

Orphan recovery: detection conditions and both branches (spec:337–344). Resume continues from **Phase 2b**, not Phase 2a — the plan already exists and must not be regenerated.

- [ ] **Step 12: Write the Phase 12 availability check**

The `superpowers:writing-plans` handoff is offered **only if superpowers is installed**. When it is not, present only implement-now and stop-here. State that the plugin must be fully functional standalone.

- [ ] **Step 13: Check the size target**

Run: `wc -l ~/Desktop/projects/spyglass/skills/spyglass/SKILL.md`
Expected: under 400. If over, apply the externalisation rule from this task's header — artefact templates out, HIL specs stay.

- [ ] **Step 14: Verify every agent reference resolves to a real file**

Run:
```bash
cd ~/Desktop/projects/spyglass
grep -o "spyglass:[a-z-]*" skills/spyglass/SKILL.md | sort -u | sed 's/spyglass://' | while read a; do
  test -f "agents/$a.md" && echo "$a OK" || echo "$a MISSING"
done
```
Expected: every line `OK`. A `MISSING` means the skill names an agent that does not exist — it will fail silently at runtime.

- [ ] **Step 15: Reload the plugin and run the first behavioural test**

Ask the user to reload so the new skill and all 11 agents register:
```
/plugin uninstall spyglass
/plugin install spyglass
```

Then, from inside `~/Desktop/projects/spyglass/tests/fixtures/sample-project/`, run:
```
/spyglass add a function that converts a timestamp string to ISO-8601 format
```

Verify each of these:

| Check | Expected |
|---|---|
| Fast-path | Announces `fast-path-add` — under 15 words, single new function |
| Artefact dir | Creates `.claude/spyglass/` **inside the fixture**, with `.gitignore` containing `*` |
| Root `.gitignore` | Unmodified — confirm with `git status` in the fixture |
| HIL-1 | **Stops and waits.** Presents slug, scope signal |
| Reduced Phase 5 | Dispatches 2 agents, not 4 |
| P1 detection | `codebase-searcher` finds `timeutils.normalise_date` as `exact` or `partial` |
| S2 | Raised, because the match is priority-1 codebase code |
| HIL-3 | **Stops and waits** before writing `pseudocode.md` |
| Terminal state | Reaches HIL-10 and stops. Does **not** begin implementing |

The two failures that matter most: **not stopping at a checkpoint**, and **touching the root `.gitignore`**. Either means the skill's wording is too weak — strengthen it and re-run before continuing.

- [ ] **Step 16: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add skills/spyglass/SKILL.md
git commit -m "feat: SKILL.md — twelve-phase design workflow with ten HIL checkpoints"
```

---

### Task 10: README and project image

**Files:**
- Create: `README.md`
- Create: `assets/spyglass.png` (user-supplied)

**Interfaces:**
- Consumes: the naming line from Global Constraints, the problems-solved table (spec:257–266), the phase flow (spec:276–302)
- Produces: the repository's front door

- [ ] **Step 1: Confirm the image exists**

Run: `test -f ~/Desktop/projects/spyglass/assets/spyglass.png && echo PRESENT || echo ABSENT`

If `ABSENT`, ask the user for the Gemini-generated image before proceeding. Do not substitute a placeholder — a broken image reference in a README is worse than no image.

- [ ] **Step 2: Write `README.md`**

Sections in this order (spec:190–201):

1. **Image** — `![Spyglass](assets/spyglass.png)`
2. **One-line description** — "Design-first Python development for Claude Code."
3. **The naming line**, verbatim from Global Constraints, immediately beneath the image
4. **What it does** — the problems-solved table (spec:257–266), condensed to the failure mode and the mechanism
5. **Installation** — the two `/plugin` commands
6. **Usage** — all five invocation forms, with the note that refactor assessment is signal-driven and neither refactor keyword is needed normally
7. **What a run looks like** — the condensed phase flow **with the HIL checkpoints visible**, so a prospective user understands it is interactive before installing. Include the cost table (spec:55–61) so agent counts are not a surprise
8. **Where artefacts go** — `.claude/spyglass/`, self-ignored, and the explicit promise that the root `.gitignore` is never touched
9. **Requirements** — a Python project; radon optional and never prompted for; no dependency on other plugins
10. **Licence** — MIT

- [ ] **Step 3: Verify the image renders and no link is broken**

Run:
```bash
cd ~/Desktop/projects/spyglass
grep -o "](.*\.png)" README.md
ls assets/
```
Expected: the referenced path exists on disk.

- [ ] **Step 4: Verify the naming line is present verbatim**

Run: `grep -c "It doesn't move you an inch" ~/Desktop/projects/spyglass/README.md`
Expected: `1`

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add README.md assets/
git commit -m "docs: README with project image and usage"
```

---

### Task 11: Move the spec into the repo and verify end-to-end

**Files:**
- Create: `docs/design-spec.md` (moved from `~/.claude/docs/superpowers/specs/`)
- Create: `docs/implementation-plan.md` (this file, moved)

**Interfaces:**
- Consumes: everything built in Tasks 1–10
- Produces: a complete, version-controlled, locally-verified plugin

- [ ] **Step 1: Move the spec and plan into the repo**

```bash
cd ~/Desktop/projects/spyglass
cp ~/.claude/docs/superpowers/specs/2026-08-12-python-design-skill-design.md docs/design-spec.md
cp ~/.claude/docs/superpowers/plans/2026-08-13-spyglass-plugin.md docs/implementation-plan.md
```

Copy rather than move — leave the originals until the repo is confirmed good.

- [ ] **Step 2: Verify the full tree**

Run:
```bash
cd ~/Desktop/projects/spyglass
find . -path ./.git -prune -o -type f -print | sort
```

Expected, at minimum: 2 manifests, 1 command, 2 skill files, 11 agents, README, LICENSE, .gitignore, 2 docs, the fixture tree, and the image.

- [ ] **Step 3: Full standard-flow behavioural test**

From inside `tests/fixtures/sample-project/`, run a task that triggers the **standard** flow rather than a fast path:

```
/spyglass add CSV export with configurable delimiter and a summary footer to the reporting module
```

Verify:

| Check | Expected |
|---|---|
| Fast-path | **Not** taken — over 15 words, multiple capabilities |
| Phase 4a → 3 → 4b | Module design precedes pattern analysis, which precedes contracts |
| P3 detection | `pattern-analyzer` reports docstring format `inconsistent` — Google in `timeutils.py`, NumPy in `report.py` |
| S4 | Raised by that inconsistency |
| HIL-2 | Presents module-design summary **and** patterns together |
| Phase 5 | All four agents dispatched in one response |
| P4 detection | `deps-searcher` finds `python-dateutil` declared in `pyproject.toml` |
| Phase 9 | Auto-runs because S4 fired — **without** the user asking |
| HIL-7 | States **which signal fired and its evidence** |
| Adopted refactors | `before-current-task` written into `pseudocode.md`; `after-current-task` into `future-tasks.md` |
| Phase 11 | `PLANS_INDEX.md` status set to `session-done`, not `complete` |
| Phase 12 | Offers the `writing-plans` handoff (superpowers is installed here) |

- [ ] **Step 4: Test the modify fast-path and S1**

```
/spyglass add a strict mode parameter to load_records
```

Verify: announces `fast-path-modify`; skips Phases 3, 5, 6, 10; **runs Phase 8**; `complexity-assessor` grades `load_records` C or worse and raises **S1**; Phase 9 auto-runs on that signal.

This is the case that proves fast-path-modify keeps refactor detection live — the whole reason Phases 8 and 9 stay in that path.

- [ ] **Step 5: Test `--complete`**

```
/spyglass --complete <slug-from-step-3>
```

Verify: drafts the summary, **presents it and waits**, and only writes `completed-summary.md` and flips `PLANS_INDEX.md` to `complete` after confirmation. Writing before confirming is a failure.

- [ ] **Step 6: Test the no-project fallback**

From a directory with no project markers, such as `~/Downloads`:
```
/spyglass add a function to parse semantic version strings
```

Verify: states plainly that it is using `~/.claude/spyglass/`, and writes the self-ignoring `.gitignore` there.

- [ ] **Step 7: Confirm the fixture's git state is clean**

Run:
```bash
cd ~/Desktop/projects/spyglass/tests/fixtures/sample-project
git status --porcelain 2>/dev/null || echo "not a git repo — check parent"
cd ~/Desktop/projects/spyglass
git status --porcelain
```

Expected: no `.claude/` entries appear as untracked. The self-ignore worked. If `.claude/spyglass/` shows up, the `.gitignore` containing `*` was not written — that is a blocking bug in Phase 1.

- [ ] **Step 8: Remove the test artefacts**

```bash
rm -rf ~/Desktop/projects/spyglass/tests/fixtures/sample-project/.claude
rm -rf ~/.claude/spyglass
```

The fixture ships clean. Generated artefacts from a verification run should not be committed.

- [ ] **Step 9: Commit**

```bash
cd ~/Desktop/projects/spyglass
git add docs/
git commit -m "docs: design spec and implementation plan"
```

- [ ] **Step 10: Report and stop**

Summarise: what was built, which behavioural checks passed, and anything that needed adjusting.

**Do not push to any remote and do not publish the marketplace.** Both are the user's explicit call. Report that the plugin is installed locally and working, and ask whether to proceed with either.

---

## Self-Review

**Spec coverage.** Walked each spec section against a task:

| Spec section | Task |
|---|---|
| The Name (9–15) | 10 (README naming line) |
| Invocation forms (25–30) | 1 (command), 9 (skill handling), 11 (tested) |
| Plugin constraints (40–51) | Global Constraints; verified in 9 and 11 |
| Cost expectations (53–61) | 10 (README) |
| Repository structure (67–94) | 1, 2, 11 |
| plugin.json / marketplace.json (96–129) | 1 |
| Installation (131–136) | 1, 10 |
| Command wrapper (138–149) | 1 |
| Agent format (151–169) | 4–8, validated by the frontmatter loop |
| Repository setup (171–205) | 1, 10, 11 |
| Artefact storage + git invisibility (209–251) | 9, verified in 11 Step 7 |
| Problems solved (255–266) | 10 |
| Phase flow (270–302) | 9 |
| Fast-path (304–321) | 9, tested in 11 Steps 3–4 |
| HIL batching (323–325) | 9 |
| `--complete` (327–335) | 9, tested in 11 Step 5 |
| Orphan recovery (337–344) | 9 |
| Refactor signals (348–363) | 9; S1/S2/S4 exercised by fixture plants |
| HIL specs (367–459) | 9 |
| Phase specs (463–776) | 9 for orchestration; 4–8 for agent behaviour |
| Agent summary (780–796) | 4–8; tool lists match exactly |
| Context handoff (800–821) | 9 |

No gaps found.

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". Two intentional deferrals, both with resolution steps rather than silent gaps: `<author>`/`<email>`/`<user>` in Task 1 (Step 9 greps for survivors and blocks the commit) and `assets/spyglass.png` in Task 10 (Step 1 blocks until the user supplies it).

**Type and name consistency.** Verified across tasks: all 11 agent filenames match their frontmatter `name`, and both match the Agent Summary at spec:784–796. Tool lists match the spec exactly, including `stdlib-searcher` carrying the narrowest harmless grant (`tools: Read`, unused) rather than omitting the key. Signal identifiers S1–S4 are used consistently in `complexity-assessor` (raises S1), `investigation-synthesiser` (raises S2), `style-checker` (confirms/clears S3), `pattern-analyzer` (raises S4), and `refactor-assessor` (consumes all four). British spelling `investigation-synthesiser` is used identically in the filename, frontmatter, spec, and every cross-reference.

**One risk worth flagging for execution.** Task 9 Step 15 and Task 11 Steps 3–6 require the user to run slash commands and observe interactive behaviour — they cannot be automated from a Bash tool. Budget for that being hands-on, and expect at least one iteration on SKILL.md wording if a checkpoint fails to stop.
