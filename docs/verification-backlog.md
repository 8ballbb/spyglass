# Verification backlog

Fixes that are committed but whose effect has not been observed in a real run,
and known gaps in the test suite. Kept because verification debt is easy to
carry silently: the code says the bug is fixed, the tests all pass, and nobody
notices that the passing tests never touched the fix.

Ordered by priority. **P1** means a user is affected today.

---

## Resolved since this list was written

- **`oversized-module`** — graded at last, 3/3. Seven attempts; the fix was the
  harness, not the case. Signal S3 is verified.
- **`force-tests`** — 4/4, including the `test-plan.md` assertion that had never
  run.
- **The abort-and-restart cycle** — runs now save progress after every turn and
  resume where they stopped, and an abort is detected on the turn it happens
  rather than after the whole list has fired at a dead session. `auto` has
  already advanced across two separate quota windows this way.
- **The HIL-10 vague-go-ahead fix** — `vague-go-ahead`, 3/3. A generic
  affirmation ("Yes, that all looks right. Continue.") now gets asked again at
  every checkpoint of the run rather than being read as the implement-now
  choice, three independent times against identical input.
- **The signal-identifier leak fix** (2026-08-29) — `S1 fired: load_records
  already scores 28`-style leaks. Fixed three times before this and verified
  never; verified now: `modify --repeat 3`, 3/3, with a signal genuinely
  firing and reported (`"load_records`, which is already dense — complexipy
  scores it 28 against a threshold of 15") without ever naming `S1`.
- **Agents dispatched as `general-purpose` instead of themselves** (2026-08-29)
  — a `modify --repeat 3` run caught every `Agent` tool call in one session
  going out as `subagent_type: general-purpose` carrying a hand-reconstructed
  imitation of `complexity-assessor`'s/`style-checker`'s/`refactor-assessor`'s
  own rules, well-formed enough to pass unnoticed until dispatch itself was
  checked against the raw stream-json rather than the flattened transcript.
  `SKILL.md` now has a "Dispatching Agents" section stating that a "Receives"
  line's agent name is the literal `subagent_type` value. Fixed the run after
  it was found: `modify --repeat 3`, 3/3, `subagent_type` confirmed correct in
  the raw JSONL each time (`tests/.transcripts/modify.raw.jsonl`, now
  persisted by `run-behavioural.py` for exactly this kind of check).
- **A checkpoint (HIL-7) naming itself** (2026-08-29) — the same shape of leak
  as the signal-identifier one above, on a different token: *"Now this is the
  batched refactor checkpoint (HIL-7)."* HIL-7's own spec now names this exact
  sentence and gives the corrected one, the treatment that made the
  signal-identifier fix hold. Verified: `modify --repeat 3`, 3/3.

## P2 — Three cases still unobserved

Most of what was added has now been seen working:

| Feature | Case | Result |
|---|---|---|
| `--verify` | `verify` | 6/6, against planted signature drift |
| `--audit` | `audit` | 4/4 — three assessors, both planted problems reached |
| `--auto` | `auto` | 4/4 — stopped for the ambiguity, reported its own decisions |
| Complexity budgets | `budget` | 3/3 |
| `decisions.md` | `decisions` | 3/3 — first run captured the dateutil fact it was built for |

Still unobserved:

| Feature | Case | Why |
|---|---|---|
| `[tool.spyglass]` | `config` | Quota; its one graded run failed on the HIL-10 bug, not the config |
| `conformance-log.md` | `conformance-log` | Quota; its own assertion passed, the run failed on contamination |

`vague-go-ahead` is resolved — see above. It reproduced a run that wrote two
files into the fixture and edited a third after being told "Yes, that all looks
right. Continue.", and was the only defect found in this project that puts a
diff in someone's repository rather than a sentence in a document.

## P2 — `--suggest-refactors` output is verified once, on one function

Working, and better than specified: a run reasoned against the tool's own plans,
recommending a different fix because *"complexipy's own two suggestions only
reach 22 combined"*.

But it has been seen on exactly one function, in one shape — three repeated
`if strict: raise` branches. A deeply nested function, or one long chain, may
produce plans that are numerous, contradictory, or too long to pass through
cleanly. Volume was 53 lines here; nothing bounds it.

**How to verify:** a fixture function with a different complexity shape, then
check the report stays legible.

---

## P3 — Suite stability is unmeasured

`--repeat` exists and has been used once. Every current green is a single
observation.

This matters more than it sounds. `no-refactor` alternated pass and fail across
four runs and looked like a plugin bug throughout; the cause was a grader that
truncated the field it depended on. A suite of single observations cannot tell a
stable pass from a lucky one.

**How to verify:** `--case all --repeat 3`. Expensive — sixty-three runs — and
best done when nothing else needs the quota.

---

## P3 — The radon path is untested

`tests/install-tools.sh` installs both tools, and the harness puts them on PATH,
so runs now exercise **complexipy**. radon is the documented fallback and no run
has used it, because complexipy is preferred and always present once installed.

**How to verify:** uninstall complexipy from `tests/.tools-venv` and run
`--case modify`. Cheap, and the fallback ordering has never been executed.

---

## Not planned

- **The by-eye fallback** is exercised constantly — every run before the tools
  venv existed used it. No further work needed.
- **`claude plugin eval`**, the official harness with an ablation baseline, is
  gated behind early access. Worth revisiting if that opens.
