# Verification backlog

Fixes that are committed but whose effect has not been observed in a real run,
and known gaps in the test suite. Kept because verification debt is easy to
carry silently: the code says the bug is fixed, the tests all pass, and nobody
notices that the passing tests never touched the fix.

Ordered by priority. **P1** means a user is affected today.

---

## P1 — The signal-identifier leak fix is unverified

**Status:** fixed three times, verified never.

Spyglass reports internal refactor signals to the user in messages like
`S1 fired: load_records already scores 28`. `S1` is bookkeeping; the user has
never seen the document that defines it.

| Attempt | What was changed | Outcome |
|---|---|---|
| 1 | HIL-7's worked example, which literally showed `"S1: parse_records is radon grade D"` as the thing to present | Leaked again, elsewhere |
| 2 | An explicit rule that this covers reporting a signal did *not* fire | Leaked again, elsewhere |
| 3 | Supplied the replacement sentence, plus "do not narrate your own transitions" | **Unverified** |

The first two attempts were prohibitions. Each closed the exact phrasing that
had been observed and left the next one open — the model needs the sentence to
say, not another thing not to say. That is the same lesson as the clarification
checkpoint, whose options all built something because its own example's options
all built something.

**How to verify:** `tests/run-behavioural.py --case modify`. It is the cheapest
case that fires a signal, and `check_no_jargon` catches the leak — that check is
how all three were found. Run it at `--repeat 3`: the second attempt passed one
run before failing the next, so a single green proves little here.

**Why P1:** it is the most visible defect remaining. It appears in normal use, on
the most common path, in a message the user reads.

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
| The HIL-10 fix | `vague-go-ahead` | Quota — **and this one is P1** |

`vague-go-ahead` is the one that matters. It reproduces a run that wrote two
files into the fixture and edited a third after being told "Yes, that all looks
right. Continue." The fix is in and unproven, and this is the only defect found
in this project that puts a diff in someone's repository rather than a sentence
in a document.

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
