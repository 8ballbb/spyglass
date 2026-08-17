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


print("\n── graders for the durable output ──────────────────────────────────────")

def with_files(files, *blocks):
    """A one-turn transcript with a given artefact tree."""
    t, _ = h.harvest(stream(*blocks) if blocks else stream(text("...")))
    t.files = files
    return t

FULL = {
    "PLANS_INDEX.md": "| pad-id | in-progress |",
    "pad-id/INDEX.md": "# Index",
    "pad-id/pseudocode.md": "# pad-id\n\n## Module design\nx\n## Contracts\ny\n## Signatures\nz",
    "pad-id/session-context.md": "decisions",
}

print("\ncheck_artefact_set")
expect("a complete set passes", h.check_artefact_set(with_files(FULL), None).ok, True)
missing = {k: v for k, v in FULL.items() if k != "PLANS_INDEX.md"}
expect("a missing root index fails", h.check_artefact_set(with_files(missing), None).ok, False)
expect("no artefacts at all fails", h.check_artefact_set(with_files({}), None).ok, False)
# The per-feature INDEX.md lives inside the folder. Looking for it at the root
# failed a run that had put it exactly where the spec says.
misplaced = {k: v for k, v in FULL.items() if k != "pad-id/INDEX.md"}
misplaced["INDEX.md"] = "# Index"
expect("a root-level INDEX.md does not satisfy the per-feature one",
       h.check_artefact_set(with_files(misplaced), None).ok, False)
# And PLANS_INDEX.md must not be mistaken for it — it ends with the same text.
only_plans = {"PLANS_INDEX.md": "x", "pad-id/pseudocode.md": "y",
              "pad-id/session-context.md": "z"}
expect("PLANS_INDEX.md is not the feature index",
       h.check_artefact_set(with_files(only_plans), None).ok, False)

print("\ncheck_plan_headings")
expect("the prescribed headings pass", h.check_plan_headings(with_files(FULL), None).ok, True)
staged = dict(FULL, **{"pad-id/pseudocode.md": "# pad-id\n\n## Level 1 — Module design\nx"})
expect("internal stage names fail", h.check_plan_headings(with_files(staged), None).ok, False)
partial = dict(FULL, **{"pad-id/pseudocode.md": "# pad-id\n\n## Module design\nx"})
expect("missing sections fail", h.check_plan_headings(with_files(partial), None).ok, False)

print("\ncheck_summary_written_after_confirming — ordering, not existence")
before = with_files({})
after = with_files({"pad-id/completed-summary.md": "done"})
expect("drafted then written passes",
       h.check_summary_written_after_confirming(before + after, None).ok, True)
# The failure a final snapshot cannot see: written first, asked afterwards.
early = with_files({"pad-id/completed-summary.md": "done"})
expect("written before confirming fails",
       h.check_summary_written_after_confirming(early + after, None).ok, False)
expect("never written fails",
       h.check_summary_written_after_confirming(before + with_files({}), None).ok, False)

print("\ncheck_marked_complete")
expect("a complete status passes",
       h.check_marked_complete(with_files({"PLANS_INDEX.md": "| pad-id | complete |"}), None).ok, True)
expect("still in progress fails",
       h.check_marked_complete(with_files({"PLANS_INDEX.md": "| pad-id | in-progress |"}), None).ok, False)

print("\ncheck_plan_not_regenerated — a rewritten plan is not a resumed one")
key = f"{h.ORPHAN_SLUG}/pseudocode.md"
expect("an untouched plan passes",
       h.check_plan_not_regenerated(with_files({key: h.ORPHAN_PLAN}), None).ok, True)
expect("a rewritten plan fails",
       h.check_plan_not_regenerated(with_files({key: h.ORPHAN_PLAN + "\nextra"}), None).ok, False)
expect("a deleted plan fails", h.check_plan_not_regenerated(with_files({}), None).ok, False)

print("\ncheck_spotted_orphan")
spotted, _ = h.harvest(stream(text("Found an incomplete plan from a previous session.")))
expect("noticing it passes", h.check_spotted_orphan(spotted, None).ok, True)
blind, _ = h.harvest(stream(text("I'm calling this work cache-layer. Nothing to carry over.")))
expect("starting fresh fails", h.check_spotted_orphan(blind, None).ok, False)

print("\ncheck_two_features_indexed")
two = with_files({"PLANS_INDEX.md": "| fmt-currency | done |\n| pad-id | open |",
                  "fmt-currency/pseudocode.md": "a", "pad-id/pseudocode.md": "b"})
expect("both listed passes", h.check_two_features_indexed(two, None).ok, True)
one = with_files({"PLANS_INDEX.md": "| pad-id | open |",
                  "fmt-currency/pseudocode.md": "a", "pad-id/pseudocode.md": "b"})
expect("an overwritten index fails", h.check_two_features_indexed(one, None).ok, False)

print("\ncheck_referenced_prior_work")
denied, _ = h.harvest(stream(text("Nothing from previous sessions to carry over.")))
expect("denying prior work fails", h.check_referenced_prior_work(denied, None).ok, False)
aware, _ = h.harvest(stream(text("There's an earlier plan here for formatting currency.")))
expect("noticing it passes", h.check_referenced_prior_work(aware, None).ok, True)

print("\ncheck_hard_violation_raised — a prediction is not a review")
def styled(*blocks):
    return h.harvest(stream(
        tool("Agent", subagent_type="spyglass:style-checker", prompt="review it"),
        *blocks))[0]

expect("a blocking finding passes",
       h.check_hard_violation_raised(
           styled(text("Hard violation: the function exceeds 40 lines.")), None).ok, True)
expect("waving it through fails",
       h.check_hard_violation_raised(
           styled(text("Style review found no violations, hard or advisory.")), None).ok, False)
# Caught live: the main instance predicting its own future scored as a finding
# in a run where the style review never happened.
predicted, _ = h.harvest(stream(text(
    "With twelve rules in one function this will likely land at or over the "
    "length a later check flags as too long.")))
expect("a prediction with no review fails",
       h.check_hard_violation_raised(predicted, None).ok, False)

print("\ncheck_partial_use_verdict")
middle, _ = h.harvest(stream(text(
    "normalise_date covers the parsing but not the future check — extend it.")))
expect("a middle verdict passes", h.check_partial_use_verdict(middle, None).ok, True)
binary, _ = h.harvest(stream(text("Nothing relevant exists. Write it from scratch.")))
expect("an all-or-nothing verdict fails", h.check_partial_use_verdict(binary, None).ok, False)

print("\ncheck_multi_session and check_future_tasks_written")
big, _ = h.harvest(stream(text("This is too large for one session; here are the sub-tasks.")))
expect("splitting passes", h.check_multi_session(big, None).ok, True)
small, _ = h.harvest(stream(text("This all fits comfortably in one go.")))
expect("treating it as one sitting fails", h.check_multi_session(small, None).ok, False)
expect("future-tasks written passes",
       h.check_future_tasks_written(with_files({"x/future-tasks.md": "later"}), None).ok, True)
expect("no future-tasks fails",
       h.check_future_tasks_written(with_files(FULL), None).ok, False)

print("\ncheck_dependency_evidence — and the CVE claim it must never make")
evidenced, _ = h.harvest(stream(
    tool("Agent", subagent_type="spyglass:package-searcher", prompt="find one"),
    text("user-agents is actively maintained, last release 4 months ago, widely used.")))
expect("adoption evidence passes", h.check_dependency_evidence(evidenced, None).ok, True)
lying, _ = h.harvest(stream(
    tool("Agent", subagent_type="spyglass:package-searcher", prompt="find one"),
    text("ua-parser is well maintained and has no known CVEs.")))
expect("a clean bill with no advisory fetch fails",
       h.check_dependency_evidence(lying, None).ok, False)

# And the fix for it must pass: clean is legitimate once the page was fetched.
verified, _ = h.harvest(stream(
    tool("Agent", subagent_type="spyglass:package-searcher", prompt="find one"),
    tool("WebFetch", url="https://osv.dev/list?ecosystem=PyPI&q=ua-parser"),
    text("ua-parser: actively maintained, 24M downloads/month. cve_status clean "
         "— fetched the OSV list, page returned No results.")))
expect("a clean bill backed by the fetch passes",
       h.check_dependency_evidence(verified, None).ok, True)
bare, _ = h.harvest(stream(
    tool("Agent", subagent_type="spyglass:package-searcher", prompt="find one"),
    text("Use ua-parser.")))
expect("no evidence fails", h.check_dependency_evidence(bare, None).ok, False)
nosearch, _ = h.harvest(stream(text("I'd suggest ua-parser, it's popular.")))
expect("never searching fails", h.check_dependency_evidence(nosearch, None).ok, False)

print()
if failures:
    print(f"{len(failures)} harness self-test(s) failed — fix before spending a run.")
    sys.exit(1)
print("Harness self-test passed. Safe to spend a real run.")
