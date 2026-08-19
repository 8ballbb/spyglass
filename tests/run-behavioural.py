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
    # A complete prior session — [prompt, *turns] — run and discarded before the
    # graded one starts. The plugin's stateful behaviour (resuming, indexing,
    # completing) only exists on a second visit to a project, and a single
    # scripted conversation can never reach it.
    setup: list[str] = field(default_factory=list)
    # Plant artefacts directly, for states a normal run does not produce — an
    # abandoned session, for instance, which by definition never finished.
    setup_fs: object = None
    # `{slug}` in the prompt or turns is replaced with the feature folder that
    # setup left behind. Slugs are generated, so a case cannot hardcode one.
    wants_slug: bool = False


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


# ── graders for the durable output ────────────────────────────────────────────
#
# Everything above grades the conversation. These grade what is left on disk
# afterwards, which is the plugin's actual product: a design someone can pick up
# in a later session. It went untested far longer than it should have.

# PLANS_INDEX.md sits at the root; everything else lives inside the feature
# folder. Worth stating precisely: an early version of this check looked for
# INDEX.md at the root and failed a run that had put it in exactly the right
# place. Matching by suffix alone is no good either — "PLANS_INDEX.md" ends with
# "INDEX.md".
ROOT_ARTEFACTS = ["PLANS_INDEX.md"]
FEATURE_ARTEFACTS = ["INDEX.md", "pseudocode.md", "session-context.md"]


def check_artefact_set(t: "Transcript", _) -> Result:
    """The files a finished run promises to leave behind."""
    have = set(t.files)
    missing = [f for f in ROOT_ARTEFACTS if f not in have]
    for name in FEATURE_ARTEFACTS:
        if not any(k.split("/")[-1] == name and "/" in k for k in have):
            missing.append(f"<slug>/{name}")
    return Result("wrote the artefacts it promises", not missing,
                  "missing: " + ", ".join(missing) if missing
                  else ", ".join(sorted(have)))


def check_plan_headings(t: "Transcript", _) -> Result:
    """The plan's own headings, which a user reads and a checkpoint echoes.

    "Level 1" names the stage of writing the plan, not a section of it. It
    leaked to a user once already, because the artefact's heading format was
    specified nowhere and the model borrowed the stage names.
    """
    plans = {k: v for k, v in t.files.items() if k.endswith("pseudocode.md")}
    if not plans:
        return Result("plan uses the prescribed headings", False, "no plan written")
    body = "\n".join(plans.values())
    stage_names = re.findall(r"^#+\s*Level [123]\b.*$", body, re.M)
    wanted = [h for h in ("## Module design", "## Contracts", "## Signatures")
              if h not in body]
    if stage_names:
        return Result("plan uses the prescribed headings", False,
                      "internal stage names as headings: " + "; ".join(stage_names[:3]))
    return Result("plan uses the prescribed headings", not wanted,
                  "missing headings: " + ", ".join(wanted) if wanted else "")


def check_summary_written_after_confirming(t: "Transcript", _) -> Result:
    """Confirmation precedes the write — a property no final snapshot can show.

    The completion flow must draft, present, wait, then write. A run that writes
    the summary and then asks looks identical at the end to one that did it in
    the right order.
    """
    steps = t.steps
    if len(steps) < 2:
        return Result("confirmed before writing the summary", False,
                      "run had fewer than two turns")
    early = any(k.endswith("completed-summary.md") for k in steps[0].files)
    late = any(k.endswith("completed-summary.md") for k in steps[-1].files)
    if early:
        return Result("confirmed before writing the summary", False,
                      "wrote it before asking — the confirmation was decorative")
    return Result("confirmed before writing the summary", late,
                  "" if late else "never wrote it, even after confirmation")


def check_marked_complete(t: "Transcript", _) -> Result:
    index = t.files.get("PLANS_INDEX.md", "")
    if not index:
        return Result("marked the feature complete", False, "no PLANS_INDEX.md")
    ok = re.search(r"complete", index, re.I)
    return Result("marked the feature complete", bool(ok),
                  "" if ok else "index never records the completed status")


ORPHAN_SLUG = "abandoned-cache-layer"
ORPHAN_PLAN = """# abandoned-cache-layer

## Module design
`src/dataflow/cache.py` — a read-through cache in front of load_records.

## Contracts
`get(key)` returns a cached record list or None. Never raises.

## Signatures
def get(key: str) -> list[dict] | None: ...
"""


def plant_orphan(cwd: Path) -> None:
    """A session abandoned between writing the plan and writing the index.

    This state cannot be produced by a normal run, because a normal run
    finishes. It is exactly the state the recovery path exists for.
    """
    d = cwd / ".claude/spyglass" / ORPHAN_SLUG
    d.mkdir(parents=True, exist_ok=True)
    (d / "pseudocode.md").write_text(ORPHAN_PLAN)
    ignore = cwd / ".claude/spyglass/.gitignore"
    if not ignore.exists():
        ignore.write_text("*\n")


def check_spotted_orphan(t: "Transcript", _) -> Result:
    said = re.search(r"incomplete|unfinished|previous session|abandoned|left off|"
                     r"already (a|an) plan|resume", t.visible, re.I)
    return Result("spotted the abandoned session", bool(said),
                  "" if said else "started fresh without noticing the existing plan")


def check_plan_not_regenerated(t: "Transcript", _) -> Result:
    """Resuming reuses the plan. It does not quietly rewrite it.

    The spec is explicit that the earlier stages are not re-run on resume, and a
    regenerated plan is the silent failure: it looks like a successful resume
    while discarding the work being resumed.
    """
    key = f"{ORPHAN_SLUG}/pseudocode.md"
    now = t.files.get(key)
    if now is None:
        return Result("kept the existing plan intact", False,
                      "the planted plan is gone")
    return Result("kept the existing plan intact", now == ORPHAN_PLAN,
                  "" if now == ORPHAN_PLAN else "the plan was rewritten rather than resumed")


def check_two_features_indexed(t: "Transcript", _) -> Result:
    """A second run in the same project appends; it does not overwrite."""
    index = t.files.get("PLANS_INDEX.md", "")
    if not index:
        return Result("indexed both pieces of work", False, "no PLANS_INDEX.md")
    slugs = {k.split("/")[0] for k in t.files if "/" in k}
    listed = [sl for sl in slugs if sl in index]
    return Result("indexed both pieces of work", len(listed) >= 2,
                  f"index lists {len(listed)} of {len(slugs)} feature folders")


def check_referenced_prior_work(t: "Transcript", _) -> Result:
    """The point of keeping notes is that the next run reads them."""
    denied = re.search(r"nothing (from|related to) previous sessions|"
                       r"no prior work|nothing to carry over", t.steps[0].visible, re.I)
    return Result("noticed the earlier work", not denied,
                  "claimed there was no prior work in a project it had already planned in"
                  if denied else "")


def check_hard_violation_raised(t: "Transcript", _) -> Result:
    """A style review that never blocks anything is decoration.

    The dispatch is part of the assertion, not a separate nicety. Without it
    this passed on the main instance predicting its own future — "this will
    likely land at or over the length a later check flags as too long" — in a
    run where the style review never happened. A promise and a finding read
    identically to a regex; only the dispatch tells them apart.
    """
    if "style-checker" not in t.full:
        return Result("raised a blocking style violation", False,
                      "no style review ran, so any mention of length is a guess")
    found = re.search(r"(hard|blocking) violation|must be fixed|"
                      r"exceeds .{0,40}(line|limit)|too (long|large)|"
                      r"split (it|this|the function)|over 40 lines",
                      t.full, re.I)
    return Result("raised a blocking style violation", bool(found),
                  "" if found else "reviewed a deliberately oversized design and found nothing")


def check_partial_use_verdict(t: "Transcript", _) -> Result:
    """The middle verdict — existing code does most of it — is the hardest one.

    "Use it" and "write it from scratch" are easy. Saying that normalise_date
    covers most of the job and naming the remainder is where a synthesis earns
    its keep, and it is what raises the near-duplicate signal.
    """
    verdict = re.search(r"partial|most of|covers .{0,30}(but|except)|"
                        r"extend|build on|reuse .{0,40}and add", t.full, re.I)
    return Result("reached a partial-use verdict", bool(verdict),
                  "" if verdict else "no middle verdict — it either adopted or ignored the existing code")


def check_multi_session(t: "Transcript", _) -> Result:
    split = re.search(r"more than one session|multi[- ]session|too (big|large) for one|"
                      r"split .{0,40}(into|across)|sub-?tasks?", t.visible, re.I)
    return Result("judged the work too big for one session", bool(split),
                  "" if split else "treated a deliberately oversized request as one sitting")


def check_future_tasks_written(t: "Transcript", _) -> Result:
    have = [k for k in t.files if k.endswith("future-tasks.md")]
    return Result("recorded the deferred work", bool(have),
                  ", ".join(have) if have else "no future-tasks.md")


def check_dependency_evidence(t: "Transcript", _) -> Result:
    """Proposing a new dependency requires evidence, and honesty about CVEs.

    This is the only agent that ingests untrusted web content, and the rule is
    that an unverified security status is never reported as clean.
    """
    if "package-searcher" not in t.full:
        return Result("backed the dependency with evidence", False,
                      "never searched for a package at all")
    evidence = re.search(r"maintained|last release|downloads|stars|widely used|"
                         r"actively|popular|adoption", t.full, re.I)
    # A clean bill is legitimate when the advisory page was actually fetched.
    # The failure is claiming one without the fetch — which is what happened,
    # and what the agent's rule now forbids. Grading every "clean" as a lie
    # fails the fix as well as the bug.
    claimed_clean = re.search(r"no known (cve|vulnerabilit)|no vulnerabilities|"
                              r"(cve|security)[^.]{0,30}clean|clean[^.]{0,20}(cve|record)",
                              t.full, re.I)
    checked = "osv.dev/list" in t.full
    if claimed_clean and not checked:
        return Result("backed the dependency with evidence", False,
                      "claimed a clean security status without fetching the advisory list")
    return Result("backed the dependency with evidence", bool(evidence),
                  "" if evidence else "proposed a package with no adoption evidence")


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
    # ── the durable output, and the stateful flows ────────────────────────────
    Case(
        name="artefacts",
        description="A finished run must leave the notes it promises, with the "
                    "plan's own headings written for a human.",
        prompt="/spyglass:spyglass add a function that formats a currency amount",
        turns=[
            "Yes, that name and size are fine. Take a float and a three-letter "
            "currency code, return a string like '1,234.50 EUR'.",
            "The plan looks right. Continue.",
            "Continue.",
            "Yes, that all looks right. Continue.",
            "Yes, that's right. Continue.",
            "Yes, write those notes.",
        ],
        checks=[
            check_no_jargon,
            check_artefact_set,
            check_plan_headings,
            check_no_implementation,
        ],
    ),
    Case(
        name="complete-flow",
        description="Completing a feature must draft, ask, and only then write.",
        setup=[
            "/spyglass:spyglass add a function that formats a currency amount",
            "Yes, that name and size are fine. Take a float and a three-letter "
            "currency code, return a string like '1,234.50 EUR'.",
            "The plan looks right. Continue.",
            "Continue.",
            "Yes, that all looks right. Continue.",
            "Yes, that's right. Continue.",
            "Yes, write those notes.",
        ],
        wants_slug=True,
        prompt="/spyglass:spyglass --complete {slug}",
        turns=["Yes, that summary is right. Write it."],
        checks=[
            check_no_jargon,
            check_summary_written_after_confirming,
            check_marked_complete,
            check_no_implementation,
        ],
    ),
    Case(
        name="orphan-resume",
        description="An abandoned plan must be spotted and resumed, not "
                    "silently regenerated.",
        setup_fs=plant_orphan,
        prompt="/spyglass:spyglass add a read-through cache in front of load_records",
        turns=["Resume from the existing plan."],
        checks=[
            check_no_jargon,
            check_spotted_orphan,
            check_plan_not_regenerated,
            check_no_implementation,
        ],
    ),
    Case(
        name="second-run",
        description="A second piece of work in the same project must be added "
                    "to the index, and the first must be noticed.",
        setup=[
            "/spyglass:spyglass add a function that formats a currency amount",
            "Yes, that name and size are fine. Take a float and a three-letter "
            "currency code, return a string like '1,234.50 EUR'.",
            "The plan looks right. Continue.",
            "Continue.",
            "Yes, that all looks right. Continue.",
            "Yes, that's right. Continue.",
            "Yes, write those notes.",
        ],
        prompt="/spyglass:spyglass add a function that pads an id to eight digits",
        turns=[
            "Yes, that name and size are fine. Pad with leading zeros.",
            "The plan looks right. Continue.",
            "Continue.",
            "Yes, that all looks right. Continue.",
            "Yes, that's right. Continue.",
            "Yes, write those notes.",
        ],
        checks=[
            check_no_jargon,
            check_referenced_prior_work,
            check_two_features_indexed,
            check_no_implementation,
        ],
    ),
    # ── phases and signals with no coverage ───────────────────────────────────
    Case(
        name="style-violation",
        description="A design that implies an oversized function must be "
                    "blocked by the style review, not waved through.",
        prompt="/spyglass:spyglass add a validate_record function that checks "
               "twelve separate field rules in one function and reports every "
               "failure it finds, with a distinct error message per rule",
        turns=[
            # The rules have to be given. An earlier version of this case asked
            # for "twelve field rules" without saying what they were, and the
            # run refused to invent business rules on the user's behalf — right,
            # and it never reached the style review the case exists to test.
            "Yes, that name works and there's no prior work. The rules: id "
            "present, id non-empty, id alphanumeric, amount present, amount "
            "numeric, amount non-negative, amount under 1e9, status present, "
            "status one of open/closed, date present, date parseable, date not "
            "in the future. Keep it as one function handling all twelve — "
            "that's what I want.",
            "The structure looks right. Continue.",
            "The plan looks right. Continue.",
            "Scope is fine as one session. Continue.",
            "Continue.",
            "Yes, that's right. Continue.",
            "Yes, that all looks right. Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("style-checker", "no style review ran at all"),
            check_hard_violation_raised,
            check_no_implementation,
        ],
    ),
    Case(
        name="partial-use",
        description="When existing code does most but not all of the job, the "
                    "synthesis must say so rather than pick a side.",
        prompt="/spyglass:spyglass add a function that converts a date string to "
               "ISO-8601 and rejects any date in the future",
        turns=[
            "Yes, that name and size are fine. Loose date strings in, ISO-8601 "
            "out, and raise if the date is after today.",
            "The plan looks right. Go ahead and check what already exists.",
            "Scope is fine as one session. Continue.",
            "Continue.",
            "Yes, that's right. Continue.",
            "Yes, that all looks right. Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("investigation-synthesiser", "no synthesis of the four reports"),
            check_partial_use_verdict,
            check_found_existing,
            check_no_implementation,
        ],
    ),
    Case(
        name="scope-split",
        description="Work too large for one session must be broken up, with the "
                    "remainder written down.",
        prompt="/spyglass:spyglass build a full ingestion pipeline: CSV and JSON "
               "loaders, a validation layer with per-field rules, retry and "
               "backoff on read failures, an on-disk cache, a reporting module "
               "with three output formats, and a command line interface",
        turns=[
            # Generic affirmations are not answers. Both of the runs that failed
            # here held out on a design-deciding question the scripted replies
            # ignored — correctly, since guessing is the failure the checkpoint
            # exists to prevent. Anticipate it instead.
            "Yes, that name works and there's no prior work. Build it as new "
            "modules alongside ingest.py — leave load_records untouched.",
            "The structure looks right. Continue.",
            "The plan looks right. Continue.",
            "Yes, that breakdown is right — do the first piece only.",
            "Continue.",
            "Yes, that's right. Continue.",
            "Yes, that all looks right. Continue.",
            "Yes, write those notes.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("scope-assessor", "never judged the size of the work"),
            check_multi_session,
            check_future_tasks_written,
            check_no_implementation,
        ],
    ),
    Case(
        name="force-refactor",
        description="The refactor keyword must force an assessment where no "
                    "signal would have fired.",
        prompt="/spyglass:spyglass --refactor add a function that pads an id to eight digits",
        turns=[
            "Yes, that name and size are fine. Pad with leading zeros.",
            "The plan looks right. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("refactor-assessor", "the keyword did not force an assessment"),
            check_no_implementation,
        ],
    ),
    Case(
        name="oversized-module",
        description="A plan that would push an existing class past its size "
                    "limit must raise that before the code is written.",
        prompt="/spyglass:spyglass add five new aggregations to ReportBuilder in "
               "report.py: median, percentile, variance, moving average and "
               "year-on-year change, each with its own formatting helper",
        turns=[
            "Yes, that name works and there's no prior work. Put them all on "
            "ReportBuilder — that's where the other aggregations live. "
            "year_on_year_change takes two pre-aggregated numbers (current, "
            "previous); percentile takes the percentile as an argument; moving "
            "average takes a window size. No date handling anywhere.",
            "The structure looks right. Continue.",
            "The plan looks right. Continue.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            agent_ran("refactor-assessor",
                      "the plan pushes an already-large class over the limit and "
                      "nothing assessed it"),
            check_no_implementation,
        ],
    ),
    Case(
        name="new-dependency",
        description="Proposing a package the project does not have requires "
                    "adoption evidence, and no invented security clearance.",
        prompt="/spyglass:spyglass add a function that parses a browser "
               "user-agent string into browser name, version and platform",
        turns=[
            "Yes, that name works and there's no prior work. Real-world "
            "user-agent strings, so it needs to handle the messy ones.",
            "The structure looks right. Continue.",
            "The plan looks right. Go ahead and check what already exists.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            check_dependency_evidence,
            check_no_implementation,
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

    `files` is the artefact tree as it stood when the turn ended. Some guarantees
    are about *when* something was written, not whether: the completion flow
    must present a draft before writing it, and a resumed plan must not be
    regenerated. Neither is visible in a final snapshot, and neither can be
    faked by a keyword.
    """
    visible: str = ""
    full: str = ""
    turns: list["Transcript"] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)

    @property
    def steps(self) -> list["Transcript"]:
        """This run's turns — or itself, if it is a single turn."""
        return self.turns or [self]

    def __add__(self, other: "Transcript") -> "Transcript":
        combined = Transcript(self.visible + "\n" + other.visible,
                              self.full + "\n" + other.full,
                              self.steps + other.steps)
        combined.files = other.files or self.files  # latest state wins
        return combined


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
                    inp = block.get("input", {}) or {}
                    # subagent_type first, and never truncated. It is serialised
                    # after a long `prompt`, so the 400-char cut below used to
                    # drop it — and whether an agent looked dispatched then
                    # depended on how long its dispatch prompt happened to be.
                    # That, not the plugin, was the source of a case that passed,
                    # failed, passed and failed against identical input.
                    who = inp.get("subagent_type", "")
                    parts.append(f"[tool:{block.get('name')}] "
                                 + (f"subagent_type={who} " if who else "")
                                 + json.dumps(inp)[:400])
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


def artefact_root(cwd: Path) -> Path:
    """Where this run's notes live — the fixture's, or the home fallback."""
    local = cwd / ".claude/spyglass"
    return local if local.is_dir() else HOME_ARTEFACTS


def feature_dirs(cwd: Path) -> list[str]:
    root = artefact_root(cwd)
    return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def snapshot(cwd: Path) -> dict[str, str]:
    """Every artefact file and its contents, keyed by path relative to the root.

    Taken after each turn. Existence at the end says nothing about ordering, and
    ordering is the whole guarantee in two of these cases: a completion summary
    must not exist before it is confirmed, and a resumed plan must come back
    byte-identical.
    """
    root = artefact_root(cwd)
    if not root.is_dir():
        return {}
    out = {}
    for f in root.rglob("*"):
        if f.is_file():
            try:
                out[str(f.relative_to(root))] = f.read_text()
            except (UnicodeDecodeError, OSError):
                out[str(f.relative_to(root))] = "<unreadable>"
    return out


def run_case(case: Case, dry: bool, model: str | None) -> bool | None:
    """True passed, False failed, None never ran.

    None is not a soft failure. A run that died before it started has no
    opinion about the plugin, and folding it into a pass rate invents one.
    """
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

    try:
        if case.setup:
            print(f"  setting up prior state ({len(case.setup)} turns, not graded)…")
            _, out0 = sh(base + [case.setup[0]], cwd=cwd)
            pre, s0 = harvest(out0)
            for turn in case.setup[1:]:
                if not s0:
                    break
                _, o = sh(base + ["--resume", s0, turn], cwd=cwd)
                more, s1 = harvest(o)
                s0 = s1 or s0
                pre = pre + more
            why = aborted(pre)
            if why:
                print(f"  ABORTED during setup — {why}.")
                return None
            (REPO / "tests/.transcripts").mkdir(exist_ok=True)
            (REPO / f"tests/.transcripts/{case.name}.setup.txt").write_text(pre.full)

        if case.setup_fs:
            case.setup_fs(cwd)

        prompt, turns = case.prompt, list(case.turns)
        if case.wants_slug:
            found = feature_dirs(cwd)
            if not found:
                print("  ! setup left no feature folder; cannot resolve {slug}")
                return None
            prompt = prompt.replace("{slug}", found[0])
            turns = [t.replace("{slug}", found[0]) for t in turns]
            print(f"  resolved slug: {found[0]}")

        print(f"  running in {cwd} (this spawns real agents and takes a few minutes)…")
        _, out = sh(base + [prompt], cwd=cwd)
        transcript, session = harvest(out)
        transcript.files = snapshot(cwd)

        for i, turn in enumerate(turns, 1):
            if not session:
                print("  ! no session id returned; cannot continue the conversation")
                return None
            print(f"  answering checkpoint {i}/{len(turns)}…")
            _, out_n = sh(base + ["--resume", session, turn], cwd=cwd)
            more, s = harvest(out_n)
            more.files = snapshot(cwd)
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
            return None

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
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="run each case N times and report the pass rate. "
                         "Intermittent behaviour is a real failure class and a "
                         "single run cannot see it: --no-refactor passed, failed, "
                         "passed, failed against identical input")
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

    tally: dict[str, list[bool | None]] = {}
    for c in selected:
        for _ in range(max(1, args.repeat)):
            tally.setdefault(c.name, []).append(
                run_case(c, args.dry_run, args.model))

    graded = {n: [r for r in runs if r is not None] for n, runs in tally.items()}
    ok = all(all(v) for v in graded.values()) and any(graded.values())
    if not args.dry_run:
        print()
        if args.repeat > 1:
            # Report the rate, not just the verdict. "3/5" and "0/5" are very
            # different bugs: one is an ambiguous instruction the model resolves
            # differently each time, the other is behaviour that simply is not
            # there.
            for name, runs in tally.items():
                done = graded[name]
                lost = len(runs) - len(done)
                note = f"  ({lost} never ran)" if lost else ""
                print(f"  {name:<14} {sum(done)}/{len(done)} passed{note}")
            print()
        if not any(graded.values()):
            print("Nothing was graded — every run died before it started.")
        else:
            print("All cases passed." if ok else "Some cases failed — see above.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
