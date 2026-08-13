# Python Standards Reference

This is the rulebook the `style-checker` agent cites when reviewing a
**design document** — pseudo-code, module descriptions, prose contracts, and
function signatures — before any Python is written.

The design-review agent never sees implementation bodies. That fact drives
the structure of this file: rules are sorted by whether they are checkable
from a design document alone (**plan stage**) or only become visible once
real code exists (**post-implementation**). Applying a post-implementation
rule at plan stage produces a phantom violation, because the thing being
checked for literally cannot appear in pseudo-code. Do not move rules across
that line.

## Plan-stage hard rules (blocking)

These are checkable directly from a signature, an estimated size, or a
stated structure in the design document. A violation blocks the checkpoint.

1. **Function estimated at > 40 lines of logic.** If the design document's
   own size estimate (or the described steps) for a function exceeds 40
   lines, flag it — the function should be split before implementation.
2. **Class estimated at > 200 lines total.** Same logic at class scope: if
   the described responsibilities and methods add up to more than 200
   lines, the class needs to be decomposed in the design, not after the
   fact.
3. **`staticmethod` where a module-level function would serve.** If a
   signature is decorated `@staticmethod` and nothing in its description
   uses the class (no access to `cls`, no relation to instance/class
   state), it should be a plain module-level function instead.
4. **Mutable default arguments in signatures**, e.g. `def f(x: list = [])`.
   Any signature in the design document with a mutable literal (`[]`, `{}`,
   `set()`, or a mutable class instance) as a default value is a blocking
   defect — this is a real Python footgun and is fully visible in a
   signature alone.

## Plan-stage design rules (advisory)

These are judgment calls visible in a design document's prose contracts and
structure, but they are advisory, not blocking — flag them as suggestions
for the author to consider, not checkpoint failures.

1. **Single responsibility per function.** A function's contract should
   describe one operation, not a chain of unrelated ones. The test is
   whether the description reads as one coherent action or as a list of
   separate actions stitched together with "and."
2. **Two-operations rule.** If a function's contract names two or more
   operations joined by "and," check whether they are actually one
   responsibility described in two clauses, or genuinely two
   responsibilities that should be split. Use this discriminating example:

   > "validates the input and returns the parsed record" is one responsibility; "writes the record to disk and sends a notification email" is two
3. **Excessive parameter count.** A signature with a large number of
   positional or keyword parameters (roughly five or more, especially
   several of the same type) is a sign the function is doing too much or
   needs a parameter object / config dataclass.
4. **Deep nesting implied by the described control flow.** If a module
   description or pseudo-code outlines several levels of nested
   conditionals or loops, flag it as a candidate for early returns, guard
   clauses, or extraction into helper functions.
5. **Unclear or overloaded naming in the design.** Module, class, and
   function names in the document should say what they do. A name that is
   generic (`Manager`, `Helper`, `process`, `handle`), or that implies one
   thing while the contract describes another, should be flagged so it can
   be fixed before code exists.

## Post-implementation only — do not flag at plan stage

These rules describe defects that only exist inside a function body. A
design document has no function bodies — no import statements, no `try`
blocks, no attribute definitions — so none of these can be legitimately
detected from pseudo-code. Flagging them at plan stage produces false
positives on every review; wait until real code exists.

1. **Imports inside functions.** Invisible at plan stage because a design
   document contains no import statements at all — imports only appear
   once a module is actually written.
2. **Bare `except:` or catching `Exception` without re-raising.** Invisible
   at plan stage because a design document has no `try`/`except` blocks —
   error handling structure only exists in the implementation.
3. **`__double_underscore__` misuse.** Invisible at plan stage because dunder
   attributes and methods are an implementation-level detail; a design
   document describes behavior and signatures, not the underlying
   attribute machinery.

## Reference rules

This section is supporting material from the Google Python Style Guide and
PEP 8 that the agent may need for context — for phrasing feedback, for
resolving a naming question, for recognizing a convention — but none of it
is itself a check the agent runs at plan stage.

- **Import grouping order:** `__future__` imports, then standard library,
  then third-party packages, then local/first-party imports — each group
  separated by a blank line, and imports within a group sorted
  lexicographically.
- **Naming table:**
  - Modules, functions, variables: `lower_with_under`
  - Classes: `CapWords`
  - Constants: `CAPS_WITH_UNDER`
  - Internal/non-public names: prefixed with a single `_`
- **Type annotation conventions:** prefer `X | None` over `Optional[X]`; do
  not annotate `self` or `cls` parameters.
- **Docstring sections:** use `Args:`, `Returns:`, and `Raises:` sections as
  applicable.
- **Line length:** 80 characters.
- **Indentation:** 4 spaces, no tabs.

## Precedence

A project convention confirmed by the user (for example, at a HIL
checkpoint) takes precedence over any default stated in this file — if the
user has explicitly agreed to a different naming scheme, line length, or
import order, that agreement wins. The one exception is the plan-stage hard
rules section: a confirmed project convention cannot be used to waive a
blocking rule (oversized function/class estimates, an unnecessary
`staticmethod`, or a mutable default argument), since those describe defects
independent of style preference, not conventions subject to negotiation.
