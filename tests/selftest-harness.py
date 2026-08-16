#!/usr/bin/env python3
"""Self-test for the behavioural harness. Costs nothing; spawns nothing.

A behavioural run takes minutes and real tokens, so a typo in the harness is an
expensive way to learn something free could have told you. This exercises the
plumbing and every grader against synthetic transcripts — including ones that
should FAIL, because a check that cannot fail is not a check.

    tests/selftest-harness.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "harness", Path(__file__).resolve().parent / "run-behavioural.py")
h = importlib.util.module_from_spec(spec)
# Register before executing: @dataclass resolves its own module via
# sys.modules, and blows up on a module that isn't there yet.
sys.modules["harness"] = h
spec.loader.exec_module(h)


def stream(*blocks: dict, parent: str | None = None) -> str:
    """Build a stream-json payload the way the CLI emits one.

    `parent` sets parent_tool_use_id, which is how the CLI marks sub-agent
    traffic — text an agent emitted, not text the user was shown.
    """
    lines = []
    for b in blocks:
        ev = {"session_id": "sess-123", "message": {"content": [b]}}
        if parent:
            ev["parent_tool_use_id"] = parent
        lines.append(json.dumps(ev))
    return "\n".join(lines)


def text(s: str) -> dict:
    return {"type": "text", "text": s}


def tool(name: str, **inp) -> dict:
    return {"type": "tool_use", "name": name, "input": inp}


failures: list[str] = []


def expect(label: str, got, want) -> None:
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}: got {got!r}, wanted {want!r}")
        failures.append(label)


print("harvest — splits what the user saw from everything emitted")
t, session = h.harvest(stream(
    text("Hello, does that name work?"),
    tool("Write", file_path="pseudocode.md", content="## Level 1 — Module design"),
))
expect("session id recovered", session, "sess-123")
expect("spoken text captured", "does that name work" in t.visible, True)
expect("tool args excluded from visible", "Level 1" in t.visible, False)
expect("tool args present in full", "Level 1" in t.full, True)

print("\nTranscript accumulation across turns (the bug that cost a live run)")
a, _ = h.harvest(stream(text("turn one")))
b, _ = h.harvest(stream(text("turn two")))
joined = a + b
expect("visible concatenates", "turn one" in joined.visible and "turn two" in joined.visible, True)
expect("full concatenates", "turn one" in joined.full and "turn two" in joined.full, True)

print("\nsub-agent traffic is not user-visible")
sub, _ = h.harvest(stream(
    text("Full contract and Level 1 plan are below, weigh the reports."),
    parent="toolu_abc"))
expect("sub-agent text excluded from visible", "Level 1" in sub.visible, False)
expect("sub-agent text kept in full", "Level 1" in sub.full, True)
expect("sub-agent jargon is not a leak", h.check_no_jargon(sub, None).ok, True)

print("\ncheck_no_jargon — grades only what the user saw")
clean, _ = h.harvest(stream(
    text("This looks small, so I'll keep the design pass light."),
    tool("Write", file_path="p.md", content="## Level 2 — Contract design"),
))
expect("artefact headings are not a leak", h.check_no_jargon(clean, None).ok, True)

leaky, _ = h.harvest(stream(text("HIL-1 — slug, prior context, Phase 4b next")))
expect("real leak is caught", h.check_no_jargon(leaky, None).ok, False)

# Caught live: the signal-id rule had a (?! ) lookahead, so an id followed by a
# space — which is nearly all of them — was graded clean.
signal, _ = h.harvest(stream(text("S1 fired — the function being touched is dense.")))
expect("a leaked signal id is caught", h.check_no_jargon(signal, None).ok, False)

bucket, _ = h.harvest(stream(text("Reads the manifest from an AWS S3 bucket.")))
expect("an S3 bucket is not a signal id", h.check_no_jargon(bucket, None).ok, True)

print("\ncheck_investigation_ran — a promise is not a finding")
promise, _ = h.harvest(stream(text("I'll check what already exists in a moment.")))
expect("forward-looking promise fails", h.check_investigation_ran(promise, None).ok, False)

ran, _ = h.harvest(stream(
    tool("Task", subagent_type="spyglass:codebase-searcher"),
    tool("Task", subagent_type="spyglass:stdlib-searcher"),
    tool("Task", subagent_type="spyglass:deps-searcher"),
))
expect("all three searchers dispatched passes", h.check_investigation_ran(ran, None).ok, True)

partial, _ = h.harvest(stream(tool("Task", subagent_type="spyglass:codebase-searcher")))
expect("missing searchers fails", h.check_investigation_ran(partial, None).ok, False)

print("\ncheck_dateutil_assessed — a reasoned verdict either way")
rejected, _ = h.harvest(stream(text(
    "python-dateutil is declared but not installed, and dateutil.parser.parse "
    "is for ambiguous date strings — not applicable to epoch seconds.")))
expect("reasoned rejection passes", h.check_dateutil_assessed(rejected, None).ok, True)

endorsed, _ = h.harvest(stream(text(
    "Use python-dateutil — it already handles every format in the contract.")))
expect("reasoned endorsement passes", h.check_dateutil_assessed(endorsed, None).ok, True)

vague, _ = h.harvest(stream(text(
    "The project depends on python-dateutil. I'll factor that in when I check.")))
expect("mention-without-verdict fails", h.check_dateutil_assessed(vague, None).ok, False)

silent, _ = h.harvest(stream(text("Nothing relevant found.")))
expect("never mentioned fails", h.check_dateutil_assessed(silent, None).ok, False)

print("\ncheck_recommends_reuse — the outcome that matters most")
reuse, _ = h.harvest(stream(text(
    "normalise_date already covers this — extend it rather than writing a new one.")))
expect("recommending reuse passes", h.check_recommends_reuse(reuse, None).ok, True)

duplicate, _ = h.harvest(stream(text(
    "There is a normalise_date in timeutils.py. I'll add a separate function.")))
expect("found-but-duplicated fails", h.check_recommends_reuse(duplicate, None).ok, False)

print("\ndispatch survives a long prompt (the flakiness that was mine, not the plugin's)")
verbose, _ = h.harvest(stream(tool(
    "Agent",
    description="Complexity assessment of load_records",
    # Real dispatch prompts run to hundreds of characters, and subagent_type is
    # serialised after them. Truncating the input dropped it, so an agent looked
    # dispatched or not depending on how wordy its prompt was.
    prompt="Assess the cyclomatic complexity of the function this task will "
           "modify. " + "Measure it carefully and report per function. " * 12,
    subagent_type="spyglass:complexity-assessor")))
expect("a long-prompt dispatch is still seen",
       h.agent_ran("complexity-assessor", "why")(verbose, None).ok, True)
expect("and does not read as skipped",
       h.agent_skipped("complexity-assessor", "why")(verbose, None).ok, False)

print("\nagent_ran / agent_skipped — the light paths are defined by what they omit")
dispatched, _ = h.harvest(stream(tool("Task", subagent_type="spyglass:complexity-assessor")))
expect("agent_ran passes when dispatched",
       h.agent_ran("complexity-assessor", "why")(dispatched, None).ok, True)
expect("agent_skipped fails when dispatched",
       h.agent_skipped("complexity-assessor", "why")(dispatched, None).ok, False)

absent, _ = h.harvest(stream(text("Nothing new is being built here.")))
expect("agent_ran fails when absent",
       h.agent_ran("complexity-assessor", "why")(absent, None).ok, False)
expect("agent_skipped passes when absent",
       h.agent_skipped("codebase-searcher", "why")(absent, None).ok, True)

print("\ncheck_complexity_reported — measured, not merely touched")
measured, _ = h.harvest(stream(text(
    "load_records has a cyclomatic complexity of 14 (grade C) across its branches.")))
expect("a graded measurement passes", h.check_complexity_reported(measured, None).ok, True)

touched, _ = h.harvest(stream(text(
    "I'll add the strict parameter to load_records and thread it through.")))
expect("touched-but-unmeasured fails", h.check_complexity_reported(touched, None).ok, False)

elsewhere, _ = h.harvest(stream(text("Complexity looks fine across the module.")))
expect("complexity talk without the function fails",
       h.check_complexity_reported(elsewhere, None).ok, False)

print("\ncheck_refactor_unasked — and it invalidates itself if the case cheats")
raised, _ = h.harvest(stream(tool("Task", subagent_type="spyglass:refactor-assessor")))
expect("unprompted assessment passes", h.check_refactor_unasked(raised, None).ok, True)

quiet, _ = h.harvest(stream(text("Complexity is 14, but I'll leave it alone.")))
expect("signal fired with no assessment fails", h.check_refactor_unasked(quiet, None).ok, False)

cheat = h.Case(name="x", prompt="/spyglass:spyglass refactor load_records",
               description="", turns=[])
expect("a case that asks for a refactor voids the check",
       h.check_refactor_unasked(raised, cheat).ok, False)

print("\ncheck_docstring_inconsistency — report the clash, don't average it")
clash, _ = h.harvest(stream(text(
    "timeutils.py uses Google-style docstrings while report.py uses NumPy style.")))
expect("naming both styles passes", h.check_docstring_inconsistency(clash, None).ok, True)

flagged, _ = h.harvest(stream(text("Docstring format: inconsistent across the package.")))
expect("naming it inconsistent passes", h.check_docstring_inconsistency(flagged, None).ok, True)

averaged, _ = h.harvest(stream(text("The project uses Google-style docstrings.")))
expect("a confident wrong pick fails", h.check_docstring_inconsistency(averaged, None).ok, False)

print("\ncheck_clarified_before_designing — right question, right turn, real ground")
opening, _ = h.harvest(stream(text("Shall I call this date-cleanup?")))
follow, _ = h.harvest(stream(
    text("There's already a normalise_date in timeutils. What should this take?")))
expect("grounded question on the second turn passes",
       h.check_clarified_before_designing(opening + follow, None).ok, True)

ploughed_on, _ = h.harvest(stream(tool("Write", file_path="pseudocode.md", content="…")))
expect("designing without asking fails",
       h.check_clarified_before_designing(opening + ploughed_on, None).ok, False)

invented, _ = h.harvest(stream(text("Should it use a DateCleaner class or a function?")))
expect("ungrounded question fails",
       h.check_clarified_before_designing(opening + invented, None).ok, False)

expect("a single-turn run fails rather than passing vacuously",
       h.check_clarified_before_designing(opening, None).ok, False)

print("\ncheck_declined_unnecessary_work — a process that can't say 'no work needed'")
declined, _ = h.harvest(stream(text(
    "load_records already takes a strict parameter and already raises. "
    "Nothing to design here.")))
expect("declining passes", h.check_declined_unnecessary_work(declined, None).ok, True)

designed, _ = h.harvest(stream(text(
    "Right — I'll add a strict parameter to load_records. First, a name for this?")))
expect("designing it anyway fails",
       h.check_declined_unnecessary_work(designed, None).ok, False)

print("\ncheck_offered_doing_nothing — 'you may not need this' has to be on the menu")
offered, _ = h.harvest(stream(text(
    "There's already a normalise_date. Options: extend it, add a batch wrapper, "
    "or use it as-is and write nothing new.")))
expect("offering the existing function passes",
       h.check_offered_doing_nothing(opening + offered, None).ok, True)

# The real second turn from the first live run of this case: three good,
# grounded options, every one of which builds something.
all_build, _ = h.harvest(stream(text(
    "There's already a normalise_date in timeutils.py. A couple of ways this "
    "could go: 1. something that handles messier input than normalise_date "
    "currently does. 2. a batch version. 3. something else entirely.")))
expect("options that all build something fails",
       h.check_offered_doing_nothing(opening + all_build, None).ok, False)

expect("never surfacing the existing function fails",
       h.check_offered_doing_nothing(opening + invented, None).ok, False)

print("\ncheck_artefacts_in_home — the directory, self-ignoring, not a feature folder")
import tempfile

sandbox = Path(tempfile.mkdtemp(prefix="selftest-home-"))
h.HOME_ARTEFACTS = sandbox / "spyglass"
expect("missing directory fails", h.check_artefacts_in_home(None, None).ok, False)

h.HOME_ARTEFACTS.mkdir(parents=True)
expect("created but exposed to git fails", h.check_artefacts_in_home(None, None).ok, False)

(h.HOME_ARTEFACTS / ".gitignore").write_text("*\n")
# No feature folder yet — a run stopped at the opening checkpoint has not
# written one, and demanding it failed a run that behaved correctly.
expect("self-ignoring directory alone passes",
       h.check_artefacts_in_home(None, None).ok, True)

print("\ncheck_said_no_project — notes the user cannot find are notes they have lost")
told, _ = h.harvest(stream(text(
    "There's no Python project here, so I'll keep these notes in ~/.claude/spyglass.")))
expect("saying where it went passes", h.check_said_no_project(told, None).ok, True)

silent_fallback, _ = h.harvest(stream(text("Right, let's design that. First, a name?")))
expect("silent fallback fails", h.check_said_no_project(silent_fallback, None).ok, False)

print("\naborted — a run that never happened must not be graded")
limited, _ = h.harvest(stream(
    text("I'm using the spyglass skill to design this before writing code."),
    text("You've hit your session limit · resets 12:40am (Europe/Dublin)")))
expect("a session limit is detected", bool(h.aborted(limited)), True)
# This is what made the guard necessary: every check reads the truncated run as
# a behavioural failure, and they are all wrong in the same confident way.
expect("and would otherwise be graded as a plugin bug",
       h.agent_ran("pattern-analyzer", "why")(limited, None).ok, False)

server_error, _ = h.harvest(stream(text("API Error: 529 overloaded")))
expect("a server error is detected", bool(h.aborted(server_error)), True)

fine, _ = h.harvest(stream(text("Here's the plan. Does the structure look right?")))
expect("a real run is not mistaken for an abort", h.aborted(fine), None)

print("\ncheck_stopped_for_input")
asked, _ = h.harvest(stream(text("Does that name work for you?")))
expect("ends on a question passes", h.check_stopped_for_input(asked, None).ok, True)
ploughed, _ = h.harvest(stream(text("Done. I have written the function.")))
expect("no question fails", h.check_stopped_for_input(ploughed, None).ok, False)

print()
if failures:
    print(f"{len(failures)} harness self-test(s) failed — fix before spending a run.")
    sys.exit(1)
print("Harness self-test passed. Safe to spend a real run.")
