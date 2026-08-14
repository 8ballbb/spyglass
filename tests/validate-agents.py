#!/usr/bin/env python3
"""Validate agent definitions against the plugin's frontmatter contract.

Stdlib only — no pyyaml, no third-party imports. Run from anywhere:

    python3 tests/validate-agents.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
SKILL_MD = ROOT / "skills" / "spyglass" / "SKILL.md"


def frontmatter(text: str) -> list[str] | None:
    """Return the frontmatter lines, or None if the delimiters are malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:i]
    return None


def check(path: Path, skill_text: str) -> list[str]:
    block = frontmatter(path.read_text(encoding="utf-8"))
    if block is None:
        return ["missing opening and/or closing '---' frontmatter delimiter"]

    fields: dict[str, str] = {}
    for line in block:
        if line.startswith("#") or ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), value.strip())

    errors = []
    name = fields.get("name")
    if not name:
        errors.append("missing 'name:'")
    elif name != path.stem:
        errors.append(f"name '{name}' does not match filename stem '{path.stem}'")
    if not fields.get("description"):
        errors.append("missing 'description:'")

    tools = fields.get("tools")
    if tools is None:
        errors.append("missing 'tools:' key (omitting it makes the agent inherit every tool)")
    elif tools.startswith("["):
        errors.append(f"'tools' is a YAML array ({tools}); use a comma-separated string")
    elif not re.fullmatch(r"[A-Za-z_][\w:-]*(\s*,\s*[A-Za-z_][\w:-]*)*", tools):
        errors.append(f"'tools' is not a comma-separated tool list: {tools!r}")

    if name and f"spyglass:{name}" not in skill_text:
        errors.append(f"never referenced as 'spyglass:{name}' in SKILL.md")
    return errors


def main() -> int:
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    failed = 0
    for path in sorted(AGENTS_DIR.glob("*.md")):
        errors = check(path, skill_text)
        failed += bool(errors)
        print(f"{'FAIL' if errors else 'PASS'}  {path.name}")
        for error in errors:
            print(f"        - {error}")
    total = len(list(AGENTS_DIR.glob("*.md")))
    print(f"\n{total - failed}/{total} agents valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
