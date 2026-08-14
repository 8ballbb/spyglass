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
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests/fixtures/sample-project"
RESET = REPO / "tests/reset-fixture.sh"

# Internal vocabulary that must never reach a user. Sourced from the
# "Speaking to the User" section of SKILL.md.
JARGON = [
    (r"\bHIL-\d", "HIL-N checkpoint numbers"),
    (r"\bPhase \d", "Phase numbers"),
    (r"\bLevel [123]\b", "Level 1/2/3 plan stages"),
    (r"fast-path-(add|modify)", "fast-path variant names"),
    (r"\bslug\b", "the word 'slug'"),
    (r"\bS[1-4]\b(?! )", "refactor signal ids"),
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
    hits = [why for pat, why in JARGON if re.search(pat, t.visible)]
    return Result("no internal vocabulary leaked", not hits,
                  "leaked: " + ", ".join(hits) if hits else "")


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
            "The plan looks right. Go ahead and check what already exists.",
            "Continue.",
        ],
        checks=[
            check_no_jargon,
            check_investigation_ran,
            check_recommends_reuse,
            check_gitignore_untouched,
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
    """
    visible: str = ""
    full: str = ""

    def __add__(self, other: "Transcript") -> "Transcript":
        return Transcript(self.visible + "\n" + other.visible,
                          self.full + "\n" + other.full)


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
        msg = ev.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    spoken.append(block.get("text", ""))
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    parts.append(f"[tool:{block.get('name')}] "
                                 + json.dumps(block.get("input", {}))[:400])
        if isinstance(ev.get("result"), str):
            spoken.append(ev["result"])
            parts.append(ev["result"])
    return Transcript("\n".join(spoken), "\n".join(parts)), session


def reset() -> None:
    code, out = sh(["bash", str(RESET)])
    if code != 0:
        print(out)
        sys.exit("fixture reset failed — refusing to run against a dirty fixture")
    shutil.rmtree(REPO / ".claude", ignore_errors=True)


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
        print(f"  would run in {FIXTURE}:")
        print("   ", " ".join(base + [repr(case.prompt)]))
        for turn in case.turns:
            print("    then --resume <id>", repr(turn))
        return True

    reset()
    print("  running (this spawns real agents and takes a few minutes)…")

    code, out = sh(base + [case.prompt], cwd=FIXTURE)
    transcript, session = harvest(out)

    for i, turn in enumerate(case.turns, 1):
        if not session:
            print("  ! no session id returned; cannot continue the conversation")
            return False
        print(f"  answering checkpoint {i}/{len(case.turns)}…")
        _, out_n = sh(base + ["--resume", session, turn], cwd=FIXTURE)
        more, s = harvest(out_n)
        session = s or session
        transcript = transcript + more

    (REPO / "tests/.last-transcript.txt").write_text(transcript.full)

    results = [c(transcript, case) for c in case.checks]
    for r in results:
        mark = "ok  " if r.ok else "FAIL"
        print(f"  {mark}  {r.name}")
        if r.detail:
            print(f"        {r.detail}")

    passed = all(r.ok for r in results)
    print(f"\n  {'PASS' if passed else 'FAIL'}  ({sum(r.ok for r in results)}/{len(results)})")
    print(f"  transcript: tests/.last-transcript.txt")
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
            print(f"  {c.name:<8} {c.description}")
            print(f"           {len(c.checks)} checks"
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
