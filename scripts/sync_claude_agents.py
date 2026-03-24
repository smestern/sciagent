#!/usr/bin/env python3
"""Sync Claude Code agent files from GitHub Copilot agent files.

Reads each ``.github/agents/*.agent.md`` and produces the corresponding
``.claude/agents/*.md`` with platform-appropriate transformations:

- YAML frontmatter: removes handoffs/argument-hint, maps tools to Claude
  format, adds ``model: sonnet``
- Body: replaces ``#tool:vscode/askQuestions`` with plain language,
  inlines the shared scientific rigor file (Claude has no instructions/
  directory equivalent)
- Naming: ``{name}.agent.md`` → ``{name}.md`` using the YAML ``name`` field

Run after editing any GitHub agent to keep Claude agents in sync::

    python scripts/sync_claude_agents.py
    python scripts/sync_claude_agents.py --dry-run

"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical tool ordering for Claude agents
_TOOL_ORDER = ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Fetch", "Terminal"]

# GitHub tool → set of Claude tool tokens
_TOOL_MAP: dict[str, list[str]] = {
    "vscode": [],
    "vscode/askQuestions": [],
    "read": ["Read"],
    "search": ["Grep", "Glob"],
    "edit": ["Write", "Edit"],
    "editFiles": ["Write", "Edit"],
    "execute": ["Bash"],
    "web/fetch": ["Fetch"],
    "fetch": ["Fetch"],
    "terminal": ["Terminal"],
    "codebase": ["Read", "Grep", "Glob"],
    "todo": [],
}


def _parse_frontmatter(text: str) -> tuple[str, str]:
    """Split a file into YAML frontmatter and body.

    Returns (frontmatter_without_delimiters, body_after_closing_---).
    """
    if not text.startswith("---"):
        return "", text
    end = text.index("\n---", 3)
    fm = text[4:end].strip()
    body = text[end + 4:]  # skip "\n---"
    return fm, body


def _extract_yaml_fields(fm: str) -> dict:
    """Minimal YAML parser for the fields we care about.

    Handles: name, description, argument-hint, tools (list), handoffs (block).
    Returns a dict with string values; tools is a list of strings.
    """
    result: dict = {}
    lines = fm.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # name / argument-hint / description (single-line)
        for key in ("name", "argument-hint"):
            if line.startswith(f"{key}:"):
                result[key] = line.split(":", 1)[1].strip()
                i += 1
                break
        else:
            # description — may be single-line or multiline (>- block scalar)
            if line.startswith("description:"):
                value = line.split(":", 1)[1].strip()
                if value.startswith(">") or value == "":
                    # Multiline block scalar — collect continuation lines
                    parts = []
                    i += 1
                    while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                        parts.append(lines[i].strip())
                        i += 1
                    result["description"] = " ".join(p for p in parts if p)
                else:
                    result["description"] = value
                    i += 1
            elif line.startswith("tools:"):
                # tools list
                tools = []
                i += 1
                while i < len(lines) and lines[i].strip().startswith("- "):
                    tools.append(lines[i].strip().lstrip("- ").strip())
                    i += 1
                result["tools"] = tools
            elif line.startswith("handoffs:"):
                # Skip the entire handoffs block
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip().startswith("- ")):
                    i += 1
            else:
                i += 1

    return result


def _map_tools(github_tools: list[str]) -> str:
    """Convert GitHub tool list to Claude comma-separated tools string."""
    seen: set[str] = set()
    ordered: list[str] = []
    for tool in github_tools:
        for mapped in _TOOL_MAP.get(tool, [tool.title()]):
            if mapped not in seen:
                seen.add(mapped)
                ordered.append(mapped)

    # Sort by canonical order
    def sort_key(t: str) -> int:
        try:
            return _TOOL_ORDER.index(t)
        except ValueError:
            return len(_TOOL_ORDER)

    ordered.sort(key=sort_key)
    return ", ".join(ordered)


def _build_frontmatter(fields: dict) -> str:
    """Build Claude-format YAML frontmatter."""
    lines = ["---"]
    lines.append(f"name: {fields['name']}")

    # Description as block scalar for readability
    desc = fields.get("description", "")
    if len(desc) > 72:
        lines.append("description: >-")
        wrapped = textwrap.wrap(desc, width=70)
        for w in wrapped:
            lines.append(f"  {w}")
    else:
        lines.append(f"description: {desc}")

    lines.append(f"tools: {fields['claude_tools']}")
    lines.append("model: sonnet")
    lines.append("---")
    return "\n".join(lines)


def _transform_body(body: str, rigor_content: str) -> str:
    """Apply platform transformations to the agent body text."""
    # Replace the rigor reference line with inlined content
    rigor_link_pattern = (
        r"Follow the \[shared scientific rigor principles\]"
        r"\([^)]+sciagent-rigor\.instructions\.md\)\."
    )
    rigor_section = f"### Scientific Rigor (Shared)\n\n{rigor_content.strip()}"
    body = re.sub(rigor_link_pattern, rigor_section, body)

    # Replace #tool:vscode/askQuestions references with plain language
    body = re.sub(
        r"`#tool:vscode/askQuestions`",
        "Ask the user",
        body,
    )
    # Also handle without backticks
    body = re.sub(
        r"#tool:vscode/askQuestions",
        "Ask the user",
        body,
    )

    return body


def sync_agent(
    github_path: Path,
    output_dir: Path,
    rigor_content: str,
    *,
    dry_run: bool = False,
) -> Path | None:
    """Convert one GitHub agent file to Claude format.

    Returns the output path, or None if dry_run.
    """
    text = github_path.read_text(encoding="utf-8")
    fm_raw, body = _parse_frontmatter(text)
    fields = _extract_yaml_fields(fm_raw)

    if "name" not in fields:
        print(f"  SKIP {github_path.name}: no 'name' in frontmatter", file=sys.stderr)
        return None

    # Map tools
    github_tools = fields.get("tools", [])
    fields["claude_tools"] = _map_tools(github_tools)

    # Build output
    new_fm = _build_frontmatter(fields)
    new_body = _transform_body(body, rigor_content)
    output_text = new_fm + "\n" + new_body

    out_path = output_dir / f"{fields['name']}.md"

    if dry_run:
        print(f"  {github_path.name}  →  {out_path.name}")
        return None

    out_path.write_text(output_text, encoding="utf-8")
    print(f"  {github_path.name}  →  {out_path.name}")
    return out_path


def main() -> None:
    default_source = REPO_ROOT / "templates" / "agents" / ".github" / "agents"
    default_rigor = (
        REPO_ROOT / "templates" / "agents" / ".github"
        / "instructions" / "sciagent-rigor.instructions.md"
    )
    default_output = REPO_ROOT / "templates" / "agents" / ".claude" / "agents"

    parser = argparse.ArgumentParser(
        description="Sync Claude agent files from GitHub agent files.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_source,
        help=f"GitHub agents directory (default: {default_source.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--rigor",
        type=Path,
        default=default_rigor,
        help="Path to shared rigor instructions file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Claude agents output directory (default: {default_output.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"ERROR: source directory not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    if not args.rigor.is_file():
        print(f"ERROR: rigor file not found: {args.rigor}", file=sys.stderr)
        sys.exit(1)

    rigor_content = args.rigor.read_text(encoding="utf-8")

    # Strip the top-level heading from rigor content since we add our own
    # heading in the body transformation
    rigor_lines = rigor_content.strip().split("\n")
    if rigor_lines and rigor_lines[0].startswith("## "):
        rigor_content = "\n".join(rigor_lines[1:]).strip()

    github_files = sorted(args.source.glob("*.agent.md"))
    if not github_files:
        print("ERROR: no *.agent.md files found in source directory", file=sys.stderr)
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    mode = "DRY RUN" if args.dry_run else "Syncing"
    print(f"{mode}: {len(github_files)} agents  ({args.source} → {args.output})\n")

    written = []
    for gf in github_files:
        result = sync_agent(gf, args.output, rigor_content, dry_run=args.dry_run)
        if result:
            written.append(result)

    if not args.dry_run:
        # Report any orphaned Claude files that don't correspond to a GitHub agent
        expected_names = set()
        for gf in github_files:
            text = gf.read_text(encoding="utf-8")
            fm_raw, _ = _parse_frontmatter(text)
            fields = _extract_yaml_fields(fm_raw)
            if "name" in fields:
                expected_names.add(f"{fields['name']}.md")

        existing = set(f.name for f in args.output.glob("*.md"))
        orphans = existing - expected_names
        if orphans:
            print(f"\nOrphaned Claude files (not in GitHub source):")
            for o in sorted(orphans):
                print(f"  ⚠  {o}")
            print("  Consider deleting these manually.")

    print(f"\nDone. {len(written)} files written." if not args.dry_run else "\nDry run complete.")


if __name__ == "__main__":
    main()
