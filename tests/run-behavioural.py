#!/usr/bin/env python3
"""Automated behavioural tests for Spyglass.

Runs the plugin headlessly against the fixture and grades the transcript plus
the filesystem side effects. Structural validation lives in validate-agents.py;
this is the layer that only a real run can prove.

Every assertion here is deterministic — string and filesystem checks, no LLM
judge. A grader that needs a model to decide whether it passed is a grader that
can disagree with itself between runs.

    tests/run-behavioural.py --list        # show cases, spend nothing
    tests/run-behavioural.py --dry-run     # show the commands, spend nothing
    tests/run-behavioural.py               # run the default case
    tests/run-behavioural.py --case all    # run everything

Each run spawns real agents and costs real tokens. Nothing runs without being
asked for.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests/fixtures/sample-project"
RESET = REPO / "tests/reset-fixture.sh"
# Where notes go when there is no project at all. Module-level so the self-test
# can point it at a temp directory and prove the check fails when it should.
HOME_ARTEFACTS = Path.home() / ".claude/spyglass"

# Internal vocabulary that must never reach a user. Sourced from the
# "Speaking to the User" section of SKILL.md.
JARGON = [
    (r"\bHIL-\d", "HIL-N checkpoint numbers"),
    (r"\bPhase \d", "Phase numbers"),
    (r"\bLevel [123]\b", "Level 1/2/3 plan stages"),
    (r"fast-path-(add|modify)", "fast-path variant names"),
    (r"\bslug\b", "the word 'slug'"),
    # Not `(?! )`: a signal id is almost always followed by a space, so that
    # lookahead meant this rule could essentially never fire, and it did not —
    # "S1 fired — the function being touched…" was graded clean. The thing
    # actually worth excluding is an S3 bucket.
    (r"(?<!AWS )\bS[1-4]\b(?! bucket)", "refactor signal ids"),
]


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Case:
    name: str
    prompt: str
    description: str
    turns: list[str] = field(default_factory=list)  # extra turns, via --resume
    checks: list = field(default_factory=list)
    # Where to run. Default is the fixture; "nowhere" means a fresh temp dir with
    # no Python marker and no .git, which is the only way to exercise the
    # no-project fallback — anywhere inside this repo resolves to this repo.
    where: str = "fixture"


def sh(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git(*args: str) -> str:
    return sh(["git", "-C", str(REPO), *args])[1].strip()


# ── checks ────────────────────────────────────────────────────────────────────

def check_skill_loaded(t: "Transcript", _) -> Result:
    ok = "spyglass skill" in t.visible.lower() or "using the spyglass" in t.visible.lower()
    return Result("skill announced itself", ok,
                  "" if ok else "no announcement found — did the skill load at all?")


def check_no_jargon(t: "Transcript", _) -> Result:
    # Deliberately `visible`: internal headings inside a design artefact are not
    # a leak — no user reads a Write tool's arguments.
    hits = []
    for pat, why in JARGON:
        m = re.search(pat, t.visible)
        if m:
            # Quote the offending text. A failure that only names the rule costs
            # an investigation to reproduce; one that shows the sentence does not.
            lo, hi = max(0, m.start() - 70), min(len(t.visible), m.end() + 70)
            excerpt = " ".join(t.visible[lo:hi].split())
            hits.append(f"{why} — …{excerpt}…")
    return Result("no internal vocabulary leaked", not hits,
                  "\n        ".join(hits) if hits else "")


def check_artefacts_in_fixture(_t: str, _) -> Result:
    here = (FIXTURE / ".claude/spyglass").is_dir()
    outer = (REPO / ".claude/spyglass").is_dir()
    if here and not outer:
        return Result("artefacts landed in the fixture", True)
    if outer:
        return Result("artefacts landed in the fixture", False,
                      "resolved to the repo root instead — nearest-marker rule regressed")
    return Result("artefacts landed in the fixture", False, "no artefact directory created")


def check_gitignore_untouched(_t: str, _) -> Result:
    dirty = git("status", "--porcelain", ".gitignore")
    return Result("root .gitignore untouched", not dirty,
                  dirty or "")


def check_self_ignored(_t: str, _) -> Result:
    dirty = [l for l in git("status", "--porcelain").splitlines() if ".claude" in l]
    return Result("artefact dir invisible to git", not dirty,
                  "; ".join(dirty) if dirty else "")


def check_no_implementation(_t: str, _) -> Result:
    """Terminal state: Spyglass designs, it never writes code."""
    dirty = [l for l in git("status", "--porcelain", "tests/fixtures").splitlines()
             if l.strip().endswith(".py")]
    return Result("no Python written (design only)", not dirty,
                  "; ".join(dirty) if dirty else "")


def check_stopped_for_input(t: "Transcript", _) -> Result:
    tail = t.visible.strip()[-400:]
    return Result("stopped and asked the user", "?" in tail,
                  "" if "?" in tail else "transcript does not end in a question")


def check_found_existing(t: "Transcript", _) -> Result:
    ok = "normalise_date" in t.full
    return Result("spotted the existing normalise_date", ok,
                  "" if ok else "never mentioned the planted near-duplicate (P1)")


def check_investigation_ran(t: "Transcript", _) -> Result:
    """The reuse phase must actually run.

    Without this, a case can pass on the skill *saying* it will check what
    exists — a forward-looking promise reads the same to a grep as a finished
    recommendation. That false green is exactly what this check exists to stop.
    """
    agents = {a for a in ("codebase-searcher", "stdlib-searcher", "deps-searcher")
              if a in t.full}
    missing = {"codebase-searcher", "stdlib-searcher", "deps-searcher"} - agents
    return Result("reuse investigation actually ran", not missing,
                  "never dispatched: " + ", ".join(sorted(missing)) if missing else
                  f"dispatched {len(agents)} searchers")


def check_recommends_reuse(t: "Transcript", _) -> Result:
    """The best outcome a design pass can reach: you do not need to write this.

    Asked for loose date-string parsing, the fixture already contains
    normalise_date doing exactly that. Recommending a new function here is the
    reimplementation failure this whole plugin exists to prevent, so this is the
    single most valuable assertion in the suite.
    """
    if "normalise_date" not in t.full:
        return Result("recommended reusing existing code", False,
                      "never found the planted near-duplicate (P1)")
    reuse = re.search(
        r"normalise_date[^.]{0,300}\b(already|reuse|use it|extend|instead|rather than|"
        r"covers|handles|no need|don't need|do not need)"
        r"|\b(reuse|extend|use the existing|instead of writing|rather than writing|"
        r"no need to write)\b[^.]{0,300}normalise_date",
        t.full, re.I)
    return Result("recommended reusing existing code", bool(reuse),
                  "" if reuse else "found it, but still proposed writing a new function")


def check_dateutil_assessed(t: "Transcript", _) -> Result:
    """The declared dependency must get a reasoned verdict — either way.

    An earlier version of this check demanded that dateutil be *recommended*.
    That was a badly designed test: the case pins the input to Unix epoch
    seconds, and dateutil parses ambiguous date strings — it genuinely does not
    apply. The skill rejected it with a correct reason and the test failed it for
    being right. What matters is that an already-installed dependency was
    considered and judged, not that it won.
    """
    if "dateutil" not in t.full.lower():
        return Result("assessed the declared python-dateutil", False,
                      "never considered it at all (P4 missed)")
    reasoned = re.search(
        r"dateutil[^.]{0,300}\b(not applicable|not needed|no third-party|semantically wrong|"
        r"use|reuse|already|instead|rather than|covers|handles|recommend|drift|not installed)"
        r"|\b(use|reuse|recommend|instead of|rather than|no need)\b[^.]{0,300}dateutil",
        t.full, re.I)
    return Result("assessed the declared python-dateutil", bool(reasoned),
                  "" if reasoned else "mentioned, but only as something it would check later")


def agent_ran(agent: str, why: str):
    """Assert a phase agent was dispatched.

    Dispatch is visible because the harvester records tool_use names and
    arguments. Agent *reports* come back as tool results, which it does not
    record — but an agent's own messages carry parent_tool_use_id and are kept in
    `full`, so its findings are gradeable too.
    """
    def check(t: "Transcript", _) -> Result:
        ok = agent in t.full
        return Result(f"dispatched {agent}", ok, "" if ok else why)
    check.__name__ = "check_ran_" + agent.replace("-", "_")
    return check


def agent_skipped(agent: str, why: str):
    """Assert a phase agent was NOT dispatched.

    The light paths are defined as much by what they skip as by what they run. A
    fast path that quietly does everything anyway is not a fast path, and no
    positive check would notice.
    """
    def check(t: "Transcript", _) -> Result:
        ok = agent not in t.full
        return Result(f"skipped {agent}", ok, "" if ok else why)
    check.__name__ = "check_skipped_" + agent.replace("-", "_")
    return check


def check_complexity_reported(t: "Transcript", _) -> Result:
    """The planted complexity (P2) must be measured and named.

    radon is deliberately not a dependency of this plugin, so this also covers
    the assessor's fallback path: it has to reach a usable answer without it.
    """
    if "load_records" not in t.full:
        return Result("measured the complexity of load_records", False,
                      "never looked at the function being modified")
    graded = re.search(
        r"load_records[\s\S]{0,250}\b(complexity|cyclomatic|grade [A-F]\b|branches)"
        r"|\b(complexity|cyclomatic|grade [A-F])\b[\s\S]{0,250}load_records",
        t.full, re.I)
    return Result("measured the complexity of load_records", bool(graded),
                  "" if graded else "touched it, but never assessed its complexity")


def check_refactor_unasked(t: "Transcript", case) -> Result:
    """Refactoring must be raised by the signal, not by the user.

    The whole design of Phase 9 is that nobody has to remember to ask. If the
    case prompt mentions refactoring, this check proves nothing — so it fails
    itself rather than reporting a pass it did not earn.
    """
    said = [case.prompt, *case.turns] if case else []
    if any("refactor" in s.lower() for s in said):
        return Result("raised refactoring unprompted", False,
                      "case prompt mentions refactoring — this check is void, rewrite the case")
    ok = "refactor-assessor" in t.full
    return Result("raised refactoring unprompted", ok,
                  "" if ok else "a signal should have fired on this file, but nothing assessed it")


def check_docstring_inconsistency(t: "Transcript", _) -> Result:
    """The planted style clash (P3) must be reported, not averaged over.

    timeutils.py is Google-style and report.py is NumPy-style. New code cannot
    follow a convention that does not exist, so the honest answer is "these
    disagree" — not a confident pick of whichever file was read first.
    """
    # Proximity, not sentence-bounding: the evidence here is filenames, and
    # `[^.]` stops dead at the dot in "report.py".
    both = re.search(r"google[\s\S]{0,200}numpy|numpy[\s\S]{0,200}google", t.full, re.I)
    named = re.search(r"inconsistent[\s\S]{0,150}docstring|docstring[\s\S]{0,150}inconsistent",
                      t.full, re.I)
    ok = bool(both or named)
    return Result("reported the clashing docstring styles", ok,
                  "" if ok else "did not report that the two files disagree (P3 missed)")


def check_clarified_before_designing(t: "Transcript", _) -> Result:
    """An ambiguous request must be clarified at the second turn, and grounded.

    Second turn specifically: the opening checkpoint already asks its own
    questions, so a run-wide search for a question mark would pass on that alone.
    Grounding means naming something really in the codebase — an invented
    alternative is a worse question than none, because it reads as informed.
    """
    steps = t.steps
    if len(steps) < 2:
        return Result("asked a grounded clarifying question", False,
                      "run had fewer than two turns")
    step = steps[1]
    real = [s for s in ("normalise_date", "timeutils", "load_records", "summarise",
                        "ingest.py", "report.py") if s in step.full]
    asked = "AskUserQuestion" in step.full or "?" in step.visible
    if not asked:
        return Result("asked a grounded clarifying question", False,
                      "went straight to designing without resolving the ambiguity")
    if not real:
        return Result("asked a grounded clarifying question", False,
                      "asked, but named nothing that actually exists in the project")
    return Result("asked a grounded clarifying question", True,
                  "grounded in " + ", ".join(real))


def check_declined_unnecessary_work(t: "Transcript", _) -> Result:
    """Asked for something that already exists, the answer is "it already does that".

    This is the cheapest possible outcome and the hardest one for a model to
    reach: the request is an instruction, the code is right there, and designing
    it anyway looks like helpfulness. A design process that cannot say "no work
    needed" will always find work.
    """
    declined = re.search(
        r"already (has|takes|does|raises|implement|support)|"
        r"nothing to (design|build|do)|nothing left to build|"
        r"no new code|no code needs to change|already what it does",
        t.visible, re.I)
    return Result("said the work was unnecessary", bool(declined),
                  "" if declined else "designed it anyway instead of saying it already exists")


def check_no_plan_written(_t, _) -> Result:
    """And it must not leave a plan behind for work it just said was unnecessary."""
    plans = list((FIXTURE / ".claude/spyglass").rglob("pseudocode.md")) \
        if (FIXTURE / ".claude/spyglass").is_dir() else []
    return Result("wrote no plan for work it declined", not plans,
                  "; ".join(str(p.relative_to(FIXTURE)) for p in plans))


def check_offered_doing_nothing(t: "Transcript", _) -> Result:
    """"You may not need this" has to be on the menu.

    A clarifying question whose every option builds something has already decided
    the interesting question. When existing code plausibly covers the job, using
    it unchanged must be offered explicitly — finding that out for the price of
    one question is the best outcome available here, and it is not reachable if
    it was never an option.
    """
    steps = t.steps
    if len(steps) < 2:
        return Result("offered using what already exists", False,
                      "run had fewer than two turns")
    step = steps[1]
    if "normalise_date" not in step.full:
        return Result("offered using what already exists", False,
                      "never surfaced the existing function at all")
    offered = re.search(
        r"\b(as[- ]is|as it stands|unchanged|already (does|covers|handles|enough)|"
        r"nothing new|no new (code|function)|don'?t need (to write|a new|anything)|"
        r"do not need (to write|a new)|use (it|normalise_date) directly|"
        r"just use (it|normalise_date)|this is already done)\b",
        step.full, re.I)
    return Result("offered using what already exists", bool(offered),
                  "" if offered else
                  "every option builds something new — 'you may not need this' was never offered")


def check_artefacts_in_home(_t, _) -> Result:
    """No project, no marker — notes belong in the home fallback, not in cwd.

    Asserts the directory and its self-ignoring .gitignore, not a feature folder:
    this case stops at the opening checkpoint, and the feature folder is not
    written until the run finishes. An earlier version demanded the folder and
    failed a run that had done exactly the right thing.

    The .gitignore is worth asserting in its own right — ~/.claude is sometimes
    kept under version control, and design notes are not something to commit to
    someone's dotfiles by surprise.
    """
    if not HOME_ARTEFACTS.is_dir():
        return Result("fell back to ~/.claude/spyglass", False, "never created it")
    ignore = HOME_ARTEFACTS / ".gitignore"
    if not ignore.is_file() or "*" not in ignore.read_text():
        return Result("fell back to ~/.claude/spyglass", False,
                      "created it, but left it exposed to git")
    listing = sorted(p.name for p in HOME_ARTEFACTS.iterdir())
    return Result("fell back to ~/.claude/spyglass", True,
                  "self-ignoring; holds " + ", ".join(listing))


def check_said_no_project(t: "Transcript", _) -> Result:
    """And it has to say so. Notes the user cannot find are notes they have lost."""
    said = re.search(r"no (python )?project|couldn't find a project|"
                     r"outside (a|any) project|~/\.claude|home directory",
                     t.visible, re.I)
    return Result("said plainly where the notes went", bool(said),
                  "" if said else "used the fallback silently — the user has no idea where they are")


# ── cases ─────────────────────────────────────────────────────────────────────

CASES = [
    Case(
        name="stops",
        description="A bare request must stop at the first checkpoint, in plain "
                    "language, without writing any code.",
        prompt="/spyglass:spyglass add a function that converts a timestamp string to ISO-8601",
        checks=[
            check_skill_loaded,
            check_no_jargon,
            check_stopped_for_input,
            check_artefacts_in_fixture,
            check_gitignore_untouched,
            check_self_ignored,
            check_no_implementation,
        ],
    ),
    Case(
        name="reuse",
        description="Carried through the checkpoints, it must surface both the "
                    "planted near-duplicate and the already-installed dependency.",
        prompt="/spyglass:spyglass add a function that converts a timestamp string to ISO-8601",
        turns=[
            "Yes, the name is fine and small is right. Treat the input as Unix "
            "epoch seconds given as a string.",
            "The plan looks right. Go ahead and check what already exists that I "
            "could build this with.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            check_found_existing,
            check_investigation_ran,
            check_dateutil_assessed,
            check_gitignore_untouched,
            check_no_implementation,
        ],
    ),
    Case(
        name="dont-write-it",
        description="When existing code already does the job, it must say so "
                    "rather than designing a duplicate.",
        prompt="/spyglass:spyglass add a function that converts a date string to ISO-8601",
        turns=[
            "Yes, that name and size are fine. The input is loose human-written "
            "date strings like '2026-01-15' or '15/01/2026' — the same kind of "
            "thing the project already deals with.",
            "Use it as it is, then — nothing new needed.",
        ],
        checks=[
            check_no_jargon,
            # This case used to require the four investigation agents. Once the
            # clarification checkpoint existed, they stopped running — it
            # recognised normalise_date at the second turn and offered to stop,
            # reaching the same answer without spending them. Demanding the
            # investigation would now fail the run for being cheaper and just as
            # right. `reuse` still covers the investigation actually running.
            check_offered_doing_nothing,
            check_recommends_reuse,
            check_no_plan_written,
            check_gitignore_untouched,
            check_no_implementation,
        ],
    ),
    Case(
        name="modify",
        description="Changing existing code takes the light path — no reuse "
                    "hunt — but still measures complexity and raises refactoring "
                    "on its own.",
        # Must be a change the fixture does not already have. An earlier version
        # of this case asked for a strict mode parameter, which load_records has
        # had all along — the run correctly refused to design it, and the case
        # proved nothing about the light path. That refusal is now its own case.
        prompt="/spyglass:spyglass add an encoding parameter to load_records",
        turns=[
            "Yes, that's the right function. It should default to utf-8 and be "
            "passed through to open().",
            "The plan looks right. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            # Nothing new is being built, so there is nothing to investigate.
            # If the searchers run here, the light path is not light.
            agent_skipped("codebase-searcher",
                          "ran the reuse hunt on a change that adds no capability"),
            agent_skipped("scope-assessor",
                          "re-checked scope on a single-parameter change"),
            agent_ran("complexity-assessor",
                      "no complexity agent — either never measured, or measured "
                      "inline on the main instance instead of delegating"),
            check_complexity_reported,
            check_refactor_unasked,
            check_gitignore_untouched,
            check_no_implementation,
        ],
    ),
    Case(
        name="no-refactor",
        description="The suppression keyword must beat a signal that really "
                    "fired, not merely one that never would have.",
        # Same request as `modify`, which is proven to fire a complexity signal
        # and raise a refactor. If this case passed against a request that never
        # triggered anything, it would prove nothing at all.
        prompt="/spyglass:spyglass --no-refactor add an encoding parameter to load_records",
        turns=[
            "Yes, that's the right function. It should default to utf-8 and be "
            "passed through to open().",
            "The plan looks right. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("complexity-assessor",
                      "no complexity agent — either skipped with the refactor phase, "
                      "or assessed inline on the main instance"),
            agent_skipped("refactor-assessor",
                          "assessed refactoring despite being told not to"),
            check_no_implementation,
        ],
    ),
    Case(
        name="force-tests",
        description="The test keyword must pull test planning onto a light path "
                    "that would otherwise skip it.",
        prompt="/spyglass:spyglass --tests add a function that formats a currency amount",
        turns=[
            "Yes, that name and size are fine. Take a float and a three-letter "
            "currency code, return a string like '1,234.50 EUR'.",
            "The plan looks right. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("test-planner", "the keyword did not force test planning"),
            check_no_implementation,
        ],
    ),
    Case(
        name="already-done",
        description="Asked for something the code already does, it must say so "
                    "and stop — not design it again.",
        # load_records has taken a `strict` parameter from the start, and it
        # already raises rather than skipping. There is nothing here to build.
        prompt="/spyglass:spyglass add a strict mode parameter to load_records",
        checks=[
            check_no_jargon,
            check_declined_unnecessary_work,
            check_no_plan_written,
            check_no_implementation,
        ],
    ),
    Case(
        name="patterns",
        description="A cross-cutting request takes the full path, and must "
                    "report that the target directory's conventions disagree.",
        prompt="/spyglass:spyglass add a validation layer to the ingest pipeline "
               "that checks each record's fields before summarising, and include "
               "the rejected records in the summary output",
        turns=[
            # This must answer the clarifying question, not just the name. An
            # earlier version answered only the name, and the run spent all five
            # turns refusing to guess — correctly, and while proving nothing
            # about the full path it was written to exercise.
            "Yes, that name works and there's no prior work on this. To answer "
            "your question: leave load_records exactly as it is — the new "
            "validation step runs after it and validates its output.",
            "The structure looks right, and yes those conventions match what I'd "
            "expect. Continue.",
            "The plan looks right. Go ahead.",
            "Scope looks fine as one piece of work. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("pattern-analyzer",
                      "wrote a multi-file plan without reading the local conventions"),
            check_docstring_inconsistency,
            # Only the full path proposes genuinely new dependencies.
            agent_ran("package-searcher", "full path skipped the PyPI search"),
            agent_ran("scope-assessor", "never judged whether this fits one session"),
            check_gitignore_untouched,
            check_no_implementation,
        ],
    ),
    Case(
        name="holds-out",
        description="Given non-answers to a question that decides the design, it "
                    "must keep asking rather than guess.",
        # Same request as `patterns`, which reliably raises a real ambiguity:
        # does the new layer replace load_records' silent drop/default, or sit
        # after it? Every reply below dodges it.
        prompt="/spyglass:spyglass add a validation layer to the ingest pipeline "
               "that checks each record's fields before summarising, and include "
               "the rejected records in the summary output",
        turns=[
            "Yes, that name works and there's no prior work on this.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            check_no_plan_written,
            check_stopped_for_input,
            check_no_implementation,
        ],
    ),
    Case(
        name="ambiguous",
        description="A request open to more than one reading must be clarified "
                    "before anything is designed.",
        prompt="/spyglass:spyglass add a function to clean up dates",
        turns=[
            "Yes, that name is fine and there's no prior work on this.",
        ],
        checks=[
            check_no_jargon,
            check_clarified_before_designing,
            check_offered_doing_nothing,
            check_gitignore_untouched,
            check_no_implementation,
        ],
    ),
    Case(
        name="no-project",
        description="Run where there is no Python project, notes go to the home "
                    "fallback — and it says so.",
        prompt="/spyglass:spyglass add a function that slugifies a string",
        where="nowhere",
        checks=[
            check_no_jargon,
            check_artefacts_in_home,
            check_said_no_project,
            check_stopped_for_input,
        ],
    ),
]


@dataclass
class Transcript:
    """Two views of a run, because checks need different surfaces.

    `visible` is only what was said TO the user. `full` additionally includes
    tool calls and their arguments. Grading user-facing language against `full`
    is wrong: a design artefact may legitimately use internal headings in its own
    body, and flagging that as a leak fails the run for something no user ever
    reads.

    `turns` keeps each turn separately, because some behaviour is only wrong at a
    particular moment. "Asked a grounded clarifying question" is true of the
    second turn or it is not true at all; searching the whole run for a question
    mark would pass on any checkpoint anywhere.
    """
    visible: str = ""
    full: str = ""
    turns: list["Transcript"] = field(default_factory=list)

    @property
    def steps(self) -> list["Transcript"]:
        """This run's turns — or itself, if it is a single turn."""
        return self.turns or [self]

    def __add__(self, other: "Transcript") -> "Transcript":
        return Transcript(self.visible + "\n" + other.visible,
                          self.full + "\n" + other.full,
                          self.steps + other.steps)


def harvest(stream: str) -> tuple[Transcript, str | None]:
    """Flatten a stream-json run into both views plus its session id."""
    spoken: list[str] = []
    parts: list[str] = []
    session: str | None = None
    for line in stream.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        session = ev.get("session_id", session)
        # Sub-agent traffic carries parent_tool_use_id. Its text is agent-to-agent
        # — dispatch prompts and reports — and no user ever reads it. Counting it
        # as user-visible flagged a synthesiser prompt saying "Level 1 plan below"
        # as a language leak, which is the harness failing the plugin for its own
        # internal wiring.
        from_subagent = bool(ev.get("parent_tool_use_id"))
        msg = ev.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
            if not from_subagent:
                spoken.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                    if not from_subagent:
                        spoken.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    parts.append(f"[tool:{block.get('name')}] "
                                 + json.dumps(block.get("input", {}))[:400])
        if isinstance(ev.get("result"), str):
            spoken.append(ev["result"])
            parts.append(ev["result"])
    return Transcript("\n".join(spoken), "\n".join(parts)), session


# Conditions that mean the run never really happened. Grading these produces
# confident, entirely fictional findings: a session-limit stop was once reported
# as four behavioural failures, including agents that were never given the
# chance to be dispatched.
ABORTED = [
    (r"session limit", "the session limit was reached mid-run"),
    (r"usage limit", "the usage limit was reached mid-run"),
    (r"rate limit", "rate limited mid-run"),
    (r"Credit balance is too low", "out of credit"),
    (r"API Error: 5\d\d", "the API returned a server error"),
]


def aborted(t: "Transcript") -> str | None:
    """Why this run cannot be graded, or None if it can.

    A failed run and a failing plugin look identical to every check here — both
    are just an absence of the expected text. The difference matters enormously,
    so it is established before anything else gets an opinion.
    """
    for pat, why in ABORTED:
        if re.search(pat, t.full, re.I):
            return why
    return None


def sync_plugin() -> None:
    """Push the working tree into the installed plugin before grading it.

    `claude plugin install` snapshots; it does not track this repo. Without this,
    a run grades whatever was last installed and reports it as the current
    behaviour — the one failure this harness cannot detect from the transcript.
    """
    code, out = sh(["bash", str(REPO / "tests/sync-plugin.sh")])
    if code != 0:
        print(out)
        sys.exit("could not sync the plugin — refusing to grade a stale install")
    print("  " + out.strip().splitlines()[0])


def reset() -> None:
    code, out = sh(["bash", str(RESET)])
    if code != 0:
        print(out)
        sys.exit("fixture reset failed — refusing to run against a dirty fixture")
    shutil.rmtree(REPO / ".claude", ignore_errors=True)


def workdir(case: Case) -> tuple[Path, Path | None]:
    """Where the case runs, plus a temp dir to clean up afterwards if any.

    "nowhere" has to be outside this repo. Anywhere inside it walks up to a
    pyproject.toml or a .git and finds a project, which is the opposite of what
    the fallback case is testing.
    """
    if case.where == "fixture":
        return FIXTURE, None
    tmp = Path(tempfile.mkdtemp(prefix="spyglass-no-project-"))
    return tmp, tmp


def run_case(case: Case, dry: bool, model: str | None) -> bool:
    print(f"\n{'─' * 78}\n{case.name}  —  {case.description}\n{'─' * 78}")

    # bypassPermissions: the fixture is disposable test data, reset before every
    # run. acceptEdits is not enough — the run stops to ask before creating its
    # notes directory, and a harness that needs a human to unblock it is not a
    # harness. stream-json: "json" returns only the final message, so anything
    # said earlier in the run — the announcement, the checkpoint text — would be
    # invisible to every check.
    base = ["claude", "-p", "--permission-mode", "bypassPermissions",
            "--output-format", "stream-json", "--verbose"]
    if model:
        base += ["--model", model]

    if dry:
        print(f"  would run in {'a fresh temp dir' if case.where == 'nowhere' else FIXTURE}:")
        print("   ", " ".join(base + [repr(case.prompt)]))
        for turn in case.turns:
            print("    then --resume <id>", repr(turn))
        return True

    sync_plugin()
    reset()
    cwd, temp = workdir(case)
    print(f"  running in {cwd} (this spawns real agents and takes a few minutes)…")

    try:
        _, out = sh(base + [case.prompt], cwd=cwd)
        transcript, session = harvest(out)

        for i, turn in enumerate(case.turns, 1):
            if not session:
                print("  ! no session id returned; cannot continue the conversation")
                return False
            print(f"  answering checkpoint {i}/{len(case.turns)}…")
            _, out_n = sh(base + ["--resume", session, turn], cwd=cwd)
            more, s = harvest(out_n)
            session = s or session
            transcript = transcript + more

        # Per case, not per run: `--case all` used to leave only the last
        # transcript on disk, so diagnosing an earlier failure meant paying for
        # the run again. The last-* names stay as a convenience for single runs.
        out_dir = REPO / "tests/.transcripts"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{case.name}.full.txt").write_text(transcript.full)
        (out_dir / f"{case.name}.visible.txt").write_text(transcript.visible)
        (REPO / "tests/.last-transcript.txt").write_text(transcript.full)
        (REPO / "tests/.last-visible.txt").write_text(transcript.visible)

        why = aborted(transcript)
        if why:
            print(f"\n  ABORTED — {why}.")
            print("  Not graded: nothing here reflects the plugin's behaviour.")
            return False

        results = [c(transcript, case) for c in case.checks]
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)

    for r in results:
        mark = "ok  " if r.ok else "FAIL"
        print(f"  {mark}  {r.name}")
        if r.detail:
            print(f"        {r.detail}")

    passed = all(r.ok for r in results)
    print(f"\n  {'PASS' if passed else 'FAIL'}  ({sum(r.ok for r in results)}/{len(results)})")
    print("  transcript: tests/.last-transcript.txt (full), "
          ".last-visible.txt (what the user saw)")
    return passed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default="stops",
                    help="case name, or 'all' (default: stops)")
    ap.add_argument("--list", action="store_true", help="list cases and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would run, spend nothing")
    ap.add_argument("--model", help="override the model for the run under test")
    args = ap.parse_args()

    if args.list:
        for c in CASES:
            print(f"  {c.name:<12} {c.description}")
            print(f"  {'':<12} {len(c.checks)} checks"
                  f"{f', {len(c.turns) + 1} turns' if c.turns else ''}")
        return

    selected = CASES if args.case == "all" else [c for c in CASES if c.name == args.case]
    if not selected:
        sys.exit(f"no such case: {args.case} (try --list)")

    if not shutil.which("claude"):
        sys.exit("claude CLI not found on PATH")

    ok = all(run_case(c, args.dry_run, args.model) for c in selected)
    if not args.dry_run:
        print()
        print("All cases passed." if ok else "Some cases failed — see above.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
