#!/usr/bin/env python3
"""Build a GitHub Copilot agent plugin from SciAgent templates.

Compiles the existing templates (agents, skills, prompts, instructions) into
the agent plugin directory format that VS Code can discover and install.

Output structure::

    <output>/
    ├── .github/plugin/plugin.json
    ├── agents/
    │   ├── analysis-planner.md
    │   ├── code-reviewer.md
    │   ├── data-qc.md
    │   ├── docs-ingestor.md
    │   ├── report-writer.md
    │   └── rigor-reviewer.md
    ├── skills/
    │   ├── scientific-rigor/SKILL.md
    │   ├── analysis-planner/SKILL.md
    │   ├── ...
    │   └── docs-ingestor/SKILL.md
    └── README.md

Usage::

    python scripts/build_plugin.py                          # default build
    python scripts/build_plugin.py -o build/plugin/sciagent  # custom output
    python scripts/build_plugin.py --dry-run                 # preview only
    python scripts/build_plugin.py --version 1.0.0 --force   # set version, overwrite

Install locally in VS Code::

    // settings.json
    "chat.plugins.paths": {
        "/path/to/build/plugin/sciagent": true
    }
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
AGENTS_SRC = TEMPLATES_DIR / "agents" / ".github" / "agents"
SKILLS_SRC = TEMPLATES_DIR / "skills"
PROMPTS_SRC = TEMPLATES_DIR / "prompts"
INSTRUCTIONS_SRC = TEMPLATES_DIR / "agents" / ".github" / "instructions"

DEFAULT_OUTPUT = REPO_ROOT / "build" / "plugin" / "sciagent"

REPLACE_PATTERN = re.compile(
    r"<!--\s*REPLACE:\s*([a-zA-Z0-9_]+)\s*[—-].*?-->",
    flags=re.DOTALL,
)

# Captures the human-readable description from unfilled REPLACE placeholders
# so we can convert them to the user-friendly <!replace ...> format.
REPLACE_HUMANIZE_RE = re.compile(
    r"<!--\s*REPLACE:\s*[a-zA-Z0-9_]+\s*[—-]\s*(.*?)\s*-->",
    flags=re.DOTALL,
)


def _humanize_unfilled_placeholders(text: str) -> str:
    """Convert remaining ``<!-- REPLACE: key — desc -->`` to user-friendly markers.

    Any REPLACE placeholder that was *not* filled by ``_apply_replacements()``
    is rewritten to::

        <!replace --- <description> --- or add a link--->

    This makes the markers visible and actionable for end-users while
    preserving the intent of each placeholder.

    Skips matches inside backtick inline code so documentation references
    are not accidentally transformed.
    """

    def _humanize_match(match: re.Match[str]) -> str:
        # Skip if inside backtick inline code
        start = match.start()
        preceding = text[:start]
        # Count backticks — odd count means we're inside inline code
        if preceding.count('`') % 2 == 1:
            return match.group(0)

        desc = match.group(1).strip()
        # Strip leading "Example:" blurb and anything after it for brevity
        example_idx = desc.find("Example:")
        if example_idx > 0:
            desc = desc[:example_idx].rstrip().rstrip(".")
        # Collapse whitespace / newlines from multiline comments
        desc = " ".join(desc.split())
        return f"<!replace --- {desc} --- or add a link--->"

    return REPLACE_HUMANIZE_RE.sub(_humanize_match, text)

# Reference to shared rigor instructions that each agent links to.
# We replace this link with the inlined content.
RIGOR_LINK_PATTERN = re.compile(
    r"Follow the \[shared scientific rigor principles\]"
    r"\([^)]*sciagent-rigor\.instructions\.md\)\.",
)

# Which prompt modules to append to each agent.
# Keys are agent stems (without extension), values are prompt filenames.
AGENT_PROMPT_MAP: dict[str, list[str]] = {
    "coordinator": ["communication_style.md", "clarification.md"],
    "analysis-planner": ["communication_style.md", "clarification.md"],
    "data-qc": [
        "communication_style.md",
        "code_execution.md",
        "incremental_execution.md",
        "clarification.md",
    ],
    "rigor-reviewer": ["communication_style.md", "clarification.md"],
    "report-writer": [
        "communication_style.md",
        "reproducible_script.md",
        "clarification.md",
    ],
    "code-reviewer": ["communication_style.md", "clarification.md"],
    "docs-ingestor": ["communication_style.md", "clarification.md"],
    "coder": [
        "communication_style.md",
        "code_execution.md",
        "incremental_execution.md",
        "reproducible_script.md",
        "clarification.md",
    ],
}


# ---------------------------------------------------------------------------
# Build profiles — compile-time agent/skill consolidation
# ---------------------------------------------------------------------------

# Each profile defines how to transform the full set of agents/skills.
#   exclude_agents  — agent stems to omit entirely from the build
#   exclude_skills  — skill directory names to omit entirely
#   merge_agents    — dict of merged-agent-name → merge spec
#   merge_skills    — dict of merged-skill-name → merge spec
#   handoff_rewrites — rewrite ``agent: <old>`` refs; None = remove handoff
#   body_rewrites   — plain-text replacements applied to agent body content

PROFILES: dict[str, dict[str, Any]] = {
    "full": {
        "exclude_agents": [],
        "exclude_skills": [],
        "merge_agents": {},
        "merge_skills": {},
        "handoff_rewrites": {},
        "body_rewrites": {},
    },
    "compact": {
        "exclude_agents": ["analysis-planner", "data-qc"],
        "exclude_skills": ["update-domain", "switch-domain"],
        "merge_agents": {
            "reviewer": {
                "sources": ["code-reviewer", "rigor-reviewer"],
                "description": (
                    "Reviews analysis code and results for correctness, "
                    "reproducibility, scientific validity, and rigor — "
                    "combining code review with scientific audit in one pass."
                ),
                "argument_hint": "Provide code or analysis results to review.",
                "tools": ["vscode", "vscode/askQuestions", "read", "search", "web/fetch"],
                "handoffs": [
                    {
                        "label": "Implement Fixes",
                        "agent": "coder",
                        "prompt": "Implement the changes recommended in the review above.",
                        "send": True,
                    },
                    {
                        "label": "Generate Report",
                        "agent": "report-writer",
                        "prompt": "Generate a structured report from the reviewed analysis.",
                        "send": False,
                    },
                ],
            },
        },
        "merge_skills": {
            "review": {
                "sources": ["code-reviewer", "rigor-reviewer"],
                "description": (
                    "Reviews analysis code and results for correctness, "
                    "reproducibility, scientific validity, and rigor — "
                    "combining code review with scientific audit in one pass."
                ),
                "section_titles": {
                    "code-reviewer": "Code Quality Review",
                    "rigor-reviewer": "Scientific Rigor Audit",
                },
            },
            "configure-domain": {
                "sources": ["configure-domain", "update-domain", "switch-domain"],
                "description": None,  # keep original description from first source
                "section_titles": {
                    "configure-domain": None,  # keep as-is, no extra header
                    "update-domain": "Incremental Update Mode",
                    "switch-domain": "Domain Switching Mode",
                },
            },
        },
        "handoff_rewrites": {
            "code-reviewer": "reviewer",
            "rigor-reviewer": "reviewer",
            "analysis-planner": {
                "agent": "coordinator",
                "prompt": (
                    "Use the /analysis-planner skill to create a step-by-step "
                    "analysis plan for the task described above. Do not write "
                    "implementation code — plan only."
                ),
            },
            "data-qc": {
                "agent": "coordinator",
                "prompt": (
                    "Use the /data-qc skill to run quality control checks on "
                    "the data identified above. Focus on QC only — do not "
                    "proceed to analysis."
                ),
            },
        },
        "body_rewrites": {
            "@analysis-planner": "the `/analysis-planner` skill (invoke with `/analysis-planner`)",
            "@data-qc": "the `/data-qc` skill (invoke with `/data-qc`)",
            "@code-reviewer": "@reviewer",
            "@rigor-reviewer": "@reviewer",
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_pyproject() -> dict[str, Any]:
    """Parse pyproject.toml and return the [project] table."""
    path = REPO_ROOT / "pyproject.toml"
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        # Python < 3.11 fallback
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            # Manual extraction of a few fields as last resort
            return _read_pyproject_fallback(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {})


def _read_pyproject_fallback(path: Path) -> dict[str, str]:
    """Regex-based fallback for extracting version/description from pyproject.toml."""
    text = path.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if m:
        result["version"] = m.group(1)
    m = re.search(r'^description\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if m:
        result["description"] = m.group(1)
    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if m:
        result["name"] = m.group(1)
    return result


def _read_replacements(path: Path | None) -> dict[str, str]:
    """Read JSON/YAML replacement map."""
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Replacements file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "YAML replacements require PyYAML. Use JSON or install pyyaml."
            ) from exc
        data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("Replacements file must contain an object/map")
    return {str(k): str(v) for k, v in data.items()}


def _apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Substitute REPLACE placeholders in *text*."""
    if not replacements:
        return text

    def _replace_match(match: re.Match[str]) -> str:
        key = match.group(1)
        return replacements.get(key, match.group(0))

    return REPLACE_PATTERN.sub(_replace_match, text)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_text_without_delimiters, body).
    If no frontmatter, returns ("", text).
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return "", text
    end = stripped.find("---", 3)
    if end == -1:
        return "", text
    # Find the closing --- (skip the opening one)
    fm = stripped[3:end].strip()
    body = stripped[end + 3:].lstrip("\n")
    return fm, body


def _write(path: Path, content: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite without --force: {path}"
        )
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------


def _collect_names(profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return sorted lists of agent stems and skill directory names, filtered by profile."""
    exclude_agents = set(profile.get("exclude_agents", []))
    exclude_skills = set(profile.get("exclude_skills", []))
    merge_agents = profile.get("merge_agents", {})
    merge_skills = profile.get("merge_skills", {})

    # Collect all source agent/skill names consumed by merges
    consumed_agents: set[str] = set()
    for spec in merge_agents.values():
        consumed_agents.update(spec["sources"])
    consumed_skills: set[str] = set()
    for spec in merge_skills.values():
        consumed_skills.update(spec["sources"])

    agent_names: list[str] = []
    if AGENTS_SRC.exists():
        for f in sorted(AGENTS_SRC.glob("*.agent.md")):
            stem = f.stem.replace(".agent", "")
            if stem in exclude_agents or stem in consumed_agents:
                continue
            agent_names.append(stem)
    # Append merged agent names
    for merged_name in sorted(merge_agents.keys()):
        agent_names.append(merged_name)
    agent_names.sort()

    skill_names: list[str] = []
    if SKILLS_SRC.exists():
        for d in sorted(SKILLS_SRC.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                name = d.name
                if name in exclude_skills or name in consumed_skills:
                    continue
                skill_names.append(name)
    # Append merged skill names (only if they're genuinely new)
    for merged_name in sorted(merge_skills.keys()):
        if merged_name not in skill_names:
            skill_names.append(merged_name)
    skill_names.sort()

    return agent_names, skill_names


def _merge_agent_bodies(
    spec: dict[str, Any],
    merged_name: str,
    replacements: dict[str, str],
    rigor_text: str,
    include_prompts: bool,
    prompt_cache: dict[str, str],
    name_prefix: str,
    fullstack_overlay: str = "",
) -> str:
    """Merge multiple agent templates into a single agent file.

    Reads each source agent, concatenates their bodies with section dividers,
    and builds unified frontmatter from the merge spec.  When *fullstack_overlay*
    is non-empty, it is appended after prompt modules.
    """
    sources = spec["sources"]
    description = spec["description"]
    tools = spec.get("tools", [])
    handoffs = spec.get("handoffs", [])
    argument_hint = spec.get("argument_hint", "")

    body_parts: list[str] = []
    rigor_inlined = False
    for src_name in sources:
        src_file = AGENTS_SRC / f"{src_name}.agent.md"
        if not src_file.exists():
            print(f"WARNING: merge source not found: {src_file}", file=sys.stderr)
            continue
        raw = src_file.read_text(encoding="utf-8")
        raw = _apply_replacements(raw, replacements)
        _, body = _split_frontmatter(raw)

        # Inline rigor instructions — only the first source gets the full
        # text; subsequent sources get a short back-reference to avoid
        # duplicating the same ~50-line policy block.
        if rigor_text:
            if not rigor_inlined:
                replacement_block = (
                    "### Shared Scientific Rigor Principles\n\n" + rigor_text
                )
                body = RIGOR_LINK_PATTERN.sub(replacement_block, body)
                rigor_inlined = True
            else:
                body = RIGOR_LINK_PATTERN.sub(
                    "See *Shared Scientific Rigor Principles* above.", body,
                )

        body_parts.append(body.strip())

    # Build merged body
    merged_body = "\n\n---\n\n".join(body_parts)

    # Append prompt modules (union of all source prompt lists, deduplicated)
    if include_prompts:
        seen_prompts: set[str] = set()
        appendices: list[str] = []
        for src_name in sources:
            for prompt_name in AGENT_PROMPT_MAP.get(src_name, []):
                if prompt_name not in seen_prompts and prompt_name in prompt_cache:
                    seen_prompts.add(prompt_name)
                    appendices.append(prompt_cache[prompt_name])
        if appendices:
            merged_body = merged_body.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(appendices) + "\n"

    # Append fullstack tool overlay when requested
    if fullstack_overlay:
        merged_body = merged_body.rstrip() + "\n\n---\n\n" + fullstack_overlay + "\n"

    # Build frontmatter
    prefixed_name = _prefixed(merged_name, name_prefix)
    fm_lines = [
        f"name: {prefixed_name}",
        f"description: {description}",
    ]
    if argument_hint:
        fm_lines.append(f"argument-hint: {argument_hint}")
    fm_lines.append("tools:")
    for t in tools:
        fm_lines.append(f"  - {t}")
    if handoffs:
        fm_lines.append("handoffs:")
        _BUILTIN_AGENTS = {"agent", "ask"}
        for ho in handoffs:
            agent_ref = ho["agent"]
            if agent_ref not in _BUILTIN_AGENTS and name_prefix:
                agent_ref = _prefixed(agent_ref, name_prefix)
            fm_lines.append(f'  - label: "{ho["label"]}"')
            fm_lines.append(f"    agent: {agent_ref}")
            fm_lines.append(f'    prompt: "{ho["prompt"]}"')
            fm_lines.append(f"    send: {'true' if ho.get('send') else 'false'}")

    fm_text = "\n".join(fm_lines)
    return f"---\n{fm_text}\n---\n\n{merged_body}"


def _merge_skill_bodies(
    spec: dict[str, Any],
    merged_name: str,
    replacements: dict[str, str],
) -> str:
    """Merge multiple skill SKILL.md files into a single skill.

    Concatenates source skill content with optional section headers.
    """
    sources = spec["sources"]
    section_titles = spec.get("section_titles", {})

    parts: list[str] = []
    for src_name in sources:
        src_file = SKILLS_SRC / src_name / "SKILL.md"
        if not src_file.exists():
            print(f"WARNING: merge skill source not found: {src_file}", file=sys.stderr)
            continue
        content = src_file.read_text(encoding="utf-8")
        content = _apply_replacements(content, replacements)
        content = _humanize_unfilled_placeholders(content)

        title = section_titles.get(src_name)
        if title:
            parts.append(f"## {title}\n\n{content.strip()}")
        else:
            parts.append(content.strip())

    return "\n\n---\n\n".join(parts) + "\n"


def _rewrite_handoffs(
    agent_files: list[Path],
    rewrites: dict[str, str | None],
    name_prefix: str,
) -> None:
    """Rewrite or remove agent handoff references in built agent files.

    For each ``agent: <name>`` in YAML frontmatter:
    - If *name* maps to a string, replace with the new agent name
    - If *name* maps to None, remove that entire handoff entry
    """
    if not rewrites:
        return

    # Build prefixed lookup: the built files have prefixed agent names
    prefixed_rewrites: dict[str, str | dict | None] = {}
    for old, new in rewrites.items():
        old_key = _prefixed(old, name_prefix) if name_prefix else old
        if new is None:
            prefixed_rewrites[old_key] = None
        elif isinstance(new, dict):
            # Skill-demoted rewrite: dict with "agent" and optional "prompt"
            prefixed_agent = _prefixed(new["agent"], name_prefix) if name_prefix else new["agent"]
            prefixed_rewrites[old_key] = {
                "agent": prefixed_agent,
                "prompt": new.get("prompt"),
            }
        else:
            prefixed_rewrites[old_key] = _prefixed(new, name_prefix) if name_prefix else new

    for agent_file in agent_files:
        content = agent_file.read_text(encoding="utf-8")
        fm_text, body = _split_frontmatter(content)
        if not fm_text:
            continue

        # Process handoffs in frontmatter line by line
        lines = fm_text.split("\n")
        new_lines: list[str] = []
        skip_until_next_entry = False
        pending_prompt_rewrite: str | None = None
        i = 0
        while i < len(lines):
            line = lines[i]

            # If a previous dict-rewrite set a prompt, apply it here
            if pending_prompt_rewrite is not None:
                prompt_match = re.match(r'^(\s+prompt:\s*)(.+)$', line)
                if prompt_match:
                    line = f'{prompt_match.group(1)}"{pending_prompt_rewrite}"'
                    pending_prompt_rewrite = None

            # Detect handoff agent reference
            agent_match = re.match(r'^(\s+agent:\s*)(.+)$', line)
            if agent_match:
                agent_name = agent_match.group(1)
                agent_val = agent_match.group(2).strip()
                if agent_val in prefixed_rewrites:
                    new_val = prefixed_rewrites[agent_val]
                    if new_val is None:
                        # Remove this entire handoff entry — backtrack to remove
                        # the preceding "- label:" line and following prompt/send lines
                        _remove_handoff_block(new_lines, lines, i)
                        # Skip forward past prompt/send lines
                        i += 1
                        while i < len(lines) and re.match(r'^\s+(prompt|send):', lines[i]):
                            i += 1
                        continue
                    elif isinstance(new_val, dict):
                        # Skill-demoted rewrite: change agent and optionally prompt.
                        # Unlike simple renames, skill-demoted handoffs are always
                        # kept even when another handoff already targets the same
                        # agent — each has a unique label and prompt.
                        rewrite_agent = new_val["agent"]
                        line = f"{agent_match.group(1)}{rewrite_agent}"
                        if new_val.get("prompt"):
                            pending_prompt_rewrite = new_val["prompt"]
                    else:
                        # Simple rename: check for duplicate
                        already_exists = any(
                            re.match(rf'^\s+agent:\s*{re.escape(new_val)}\s*$', nl)
                            for nl in new_lines
                        )
                        if already_exists:
                            # Remove duplicate handoff block
                            _remove_handoff_block(new_lines, lines, i)
                            i += 1
                            while i < len(lines) and re.match(r'^\s+(prompt|send):', lines[i]):
                                i += 1
                            continue
                        line = f"{agent_match.group(1)}{new_val}"

            new_lines.append(line)
            i += 1

        new_fm = "\n".join(new_lines)
        output = f"---\n{new_fm}\n---\n\n{body}"
        agent_file.write_text(output, encoding="utf-8")


def _remove_handoff_block(new_lines: list[str], lines: list[str], agent_line_idx: int) -> None:
    """Remove a handoff block from new_lines by backtracking to the ``- label:`` line."""
    # Backtrack in new_lines to find the "- label:" line for this handoff
    while new_lines and not re.match(r'^\s+-\s*label:', new_lines[-1]):
        new_lines.pop()
    if new_lines and re.match(r'^\s+-\s*label:', new_lines[-1]):
        new_lines.pop()


def _apply_body_rewrites(
    agent_files: list[Path],
    body_rewrites: dict[str, str],
    name_prefix: str,
) -> None:
    """Apply plain-text substitutions to agent body content (not frontmatter)."""
    if not body_rewrites:
        return

    # Build prefixed rewrites for @agent references
    prefixed_body_rewrites: dict[str, str] = {}
    for old, new in body_rewrites.items():
        # If the old text starts with @, prefix the agent name portion
        if old.startswith("@") and name_prefix:
            old_prefixed = f"@{_prefixed(old[1:], name_prefix)}"
        else:
            old_prefixed = old
        # If replacement contains @agent ref, prefix it too
        if new.startswith("@") and name_prefix:
            new_prefixed = f"@{_prefixed(new[1:], name_prefix)}"
        else:
            new_prefixed = new
        prefixed_body_rewrites[old_prefixed] = new_prefixed

    for agent_file in agent_files:
        content = agent_file.read_text(encoding="utf-8")
        fm_text, body = _split_frontmatter(content)

        changed = False
        for old, new in prefixed_body_rewrites.items():
            if old in body:
                body = body.replace(old, new)
                changed = True

        if changed:
            output = f"---\n{fm_text}\n---\n\n{body}"
            agent_file.write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Routing-table rewriter (coordinator body)
# ---------------------------------------------------------------------------

# Matches a markdown table row with a bold agent name in the second column:
#   | <need> | **<agent-stem>** | <when> |
_ROUTING_ROW_RE = re.compile(
    r'^\|\s*(?P<need>[^|]+?)\s*\|\s*\*\*(?P<agent>[^*]+)\*\*\s*\|\s*(?P<when>[^|]+?)\s*\|$'
)


def _rewrite_routing_table(
    agent_files: list[Path],
    profile: dict[str, Any],
    name_prefix: str,
    skill_names: list[str] | None = None,
) -> None:
    """Rewrite the coordinator's routing table to match built agent names.

    Applies four transformations to table rows:
    1. **Exclude** — rows for excluded agents are dropped.
    2. **Skill-demote** — rows for excluded agents that still have a
       matching skill are kept, with the Agent column rewritten to
       reference the ``/skill-name`` slash command.
    3. **Merge** — rows whose agent was consumed by a merge are renamed;
       when two source rows map to the same merged name the rows are
       combined into one (Need descriptions joined with " & ").
    4. **Prefix** — surviving agent names get the build prefix.
    """
    skill_set = set(skill_names) if skill_names else set()
    exclude_agents = set(profile.get("exclude_agents", []))
    merge_agents: dict[str, Any] = profile.get("merge_agents", {})

    # Build source-agent → merged-name lookup
    source_to_merged: dict[str, str] = {}
    for merged_name, spec in merge_agents.items():
        for src in spec["sources"]:
            source_to_merged[src] = merged_name

    # Identify the coordinator file
    coord_stem = _prefixed("coordinator", name_prefix)
    coord_file: Path | None = None
    for f in agent_files:
        if f.stem == coord_stem:
            coord_file = f
            break
    if coord_file is None:
        return

    content = coord_file.read_text(encoding="utf-8")
    fm_text, body = _split_frontmatter(content)
    if not body:
        return

    lines = body.split("\n")
    new_lines: list[str] = []
    # Track merged rows so we can combine duplicates
    # key = final display name, value = index into new_lines
    seen_merged: dict[str, int] = {}

    for line in lines:
        m = _ROUTING_ROW_RE.match(line)
        if not m:
            new_lines.append(line)
            continue

        agent_stem = m.group("agent").strip()
        need = m.group("need").strip()
        when = m.group("when").strip()

        # Drop excluded agents — unless a matching skill exists
        if agent_stem in exclude_agents:
            if agent_stem in skill_set:
                # Skill-demoted: rewrite row to reference the skill
                skill_ref = f"`/{agent_stem}` skill"
                row = f"| {need} | {skill_ref} | {when} — invoke with `/{agent_stem}` |"
                new_lines.append(row)
            continue

        # Rename merged agents
        if agent_stem in source_to_merged:
            agent_stem = source_to_merged[agent_stem]

        # Apply prefix
        display_name = _prefixed(agent_stem, name_prefix)

        # Combine rows that map to the same final name
        if display_name in seen_merged:
            idx = seen_merged[display_name]
            prev = _ROUTING_ROW_RE.match(new_lines[idx])
            if prev:
                combined_need = f"{prev.group('need').strip()} & {need}"
                combined_when = f"{prev.group('when').strip()}; {when.lower()}"
                new_lines[idx] = (
                    f"| {combined_need} | **{display_name}** | {combined_when} |"
                )
            continue

        row = f"| {need} | **{display_name}** | {when} |"
        seen_merged[display_name] = len(new_lines)
        new_lines.append(row)

    new_body = "\n".join(new_lines)
    output_text = f"---\n{fm_text}\n---\n\n{new_body}"
    coord_file.write_text(output_text, encoding="utf-8")


def _build_plugin_json(
    output: Path,
    version: str,
    project_meta: dict[str, Any],
    agent_names: list[str],
    skill_names: list[str],
    name_prefix: str,
    force: bool,
) -> Path:
    """Generate .github/plugin/plugin.json."""
    description = project_meta.get(
        "description",
        "Scientific analysis agents with built-in rigor enforcement — "
        "planning, data QC, code review, reporting, and reproducibility.",
    )
    authors = project_meta.get("authors", [])
    author_name = authors[0].get("name", "SciAgent") if authors else "SciAgent"

    plugin = {
        "name": "sciagent",
        "description": description,
        "version": version,
        "author": {"name": author_name},
        "repository": "https://github.com/smestern/sciagent",
        "license": "MIT",
        "keywords": [
            "scientific-analysis",
            "data-analysis",
            "rigor",
            "reproducibility",
            "data-qc",
            "code-review",
            "report-writing",
        ],
        "agents": [
            f"./agents/{_prefixed(name, name_prefix)}.md"
            for name in agent_names
        ],
        "skills": [f"./skills/{name}" for name in skill_names],
    }

    path = output / ".github" / "plugin" / "plugin.json"
    _write(path, json.dumps(plugin, indent=2) + "\n", force)
    return path


def _prefixed(name: str, prefix: str) -> str:
    """Return *name* with *prefix*- prepended, or *name* unchanged if prefix is empty."""
    if prefix:
        return f"{prefix}-{name}"
    return name


def _build_agents(
    output: Path,
    replacements: dict[str, str],
    include_prompts: bool,
    name_prefix: str,
    force: bool,
    profile: dict[str, Any] | None = None,
    fullstack: bool = False,
) -> list[Path]:
    """Compile agent .agent.md files → agents/<name>.md with inlined instructions.

    When *profile* is provided, excluded agents are skipped, consumed agents
    (used as merge sources) are skipped, and merged agents are emitted.

    When *fullstack* is True, the fullstack tool overlay (execute_code,
    save_reproducible_script, OUTPUT_DIR, etc.) is appended to each agent.
    """
    if profile is None:
        profile = PROFILES["full"]

    exclude_agents = set(profile.get("exclude_agents", []))
    merge_agents = profile.get("merge_agents", {})

    consumed: set[str] = set()
    for spec in merge_agents.values():
        consumed.update(spec["sources"])

    rigor_text = ""
    rigor_path = INSTRUCTIONS_SRC / "sciagent-rigor.instructions.md"
    if rigor_path.exists():
        rigor_text = rigor_path.read_text(encoding="utf-8").strip()

    # Load fullstack overlay if requested
    fullstack_overlay = ""
    if fullstack:
        overlay_path = TEMPLATES_DIR / "prompts" / "overlays" / "fullstack_tools.md"
        if overlay_path.exists():
            fullstack_overlay = overlay_path.read_text(encoding="utf-8").strip()
        else:
            print(f"WARNING: --fullstack set but overlay not found: {overlay_path}", file=sys.stderr)

    # Pre-load prompt modules
    prompt_cache: dict[str, str] = {}
    if include_prompts and PROMPTS_SRC.exists():
        for p in PROMPTS_SRC.iterdir():
            if p.suffix == ".md" and p.is_file():
                content = p.read_text(encoding="utf-8").strip()
                # Strip any YAML frontmatter from prompts
                _, body = _split_frontmatter(content)
                prompt_cache[p.name] = body.strip() if body.strip() else content

    written: list[Path] = []
    if not AGENTS_SRC.exists():
        print(f"WARNING: agents source not found: {AGENTS_SRC}", file=sys.stderr)
        return written

    # Emit merged agents first
    for merged_name, spec in sorted(merge_agents.items()):
        merged_content = _merge_agent_bodies(
            spec, merged_name, replacements, rigor_text,
            include_prompts, prompt_cache, name_prefix,
            fullstack_overlay=fullstack_overlay,
        )
        prefixed_stem = _prefixed(merged_name, name_prefix)
        dest = output / "agents" / f"{prefixed_stem}.md"
        _write(dest, merged_content, force)
        written.append(dest)

    # Emit remaining individual agents
    for src_file in sorted(AGENTS_SRC.glob("*.agent.md")):
        raw = src_file.read_text(encoding="utf-8")
        raw = _apply_replacements(raw, replacements)

        fm_text, body = _split_frontmatter(raw)

        agent_stem = src_file.stem.replace(".agent", "")

        # Skip excluded or consumed agents
        if agent_stem in exclude_agents or agent_stem in consumed:
            continue

        # Replace the rigor-instructions link with inlined content
        if rigor_text:
            replacement_block = (
                "### Shared Scientific Rigor Principles\n\n" + rigor_text
            )
            body = RIGOR_LINK_PATTERN.sub(replacement_block, body)

        # Append relevant prompt modules
        if include_prompts and agent_stem in AGENT_PROMPT_MAP:
            appendices: list[str] = []
            for prompt_name in AGENT_PROMPT_MAP[agent_stem]:
                if prompt_name in prompt_cache:
                    appendices.append(prompt_cache[prompt_name])
            if appendices:
                body = body.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(appendices) + "\n"

        # Append fullstack tool overlay when requested
        if fullstack_overlay:
            body = body.rstrip() + "\n\n---\n\n" + fullstack_overlay + "\n"

        # Apply name prefix to frontmatter
        prefixed_stem = _prefixed(agent_stem, name_prefix)
        fm_text = re.sub(
            r'^(name:\s*).+$',
            rf'\g<1>{prefixed_stem}',
            fm_text,
            flags=re.MULTILINE,
        )

        # Prefix agent references in handoffs so cross-references stay consistent.
        # Built-in VS Code agent names (e.g. "agent", "ask") are left unchanged.
        _BUILTIN_AGENTS = {"agent", "ask"}
        if name_prefix:
            fm_text = re.sub(
                r'^(\s*agent:\s*)(.+)$',
                lambda m: (
                    f"{m.group(1)}{m.group(2).strip()}"
                    if m.group(2).strip() in _BUILTIN_AGENTS
                    else f"{m.group(1)}{_prefixed(m.group(2).strip(), name_prefix)}"
                ),
                fm_text,
                flags=re.MULTILINE,
            )

        # Reassemble with frontmatter
        output_content = f"---\n{fm_text}\n---\n\n{body}"

        dest = output / "agents" / f"{prefixed_stem}.md"
        _write(dest, output_content, force)
        written.append(dest)

    return written


def _build_skills(
    output: Path,
    replacements: dict[str, str],
    force: bool,
    profile: dict[str, Any] | None = None,
) -> list[Path]:
    """Copy skill directories, applying replacements to SKILL.md files.

    When *profile* is provided, excluded skills are skipped, consumed skills
    (used as merge sources) are skipped, and merged skills are emitted.
    """
    if profile is None:
        profile = PROFILES["full"]

    exclude_skills = set(profile.get("exclude_skills", []))
    merge_skills = profile.get("merge_skills", {})

    consumed: set[str] = set()
    for spec in merge_skills.values():
        consumed.update(spec["sources"])

    written: list[Path] = []
    if not SKILLS_SRC.exists():
        print(f"WARNING: skills source not found: {SKILLS_SRC}", file=sys.stderr)
        return written

    # Emit merged skills first
    for merged_name, spec in sorted(merge_skills.items()):
        merged_content = _merge_skill_bodies(spec, merged_name, replacements)
        dest = output / "skills" / merged_name / "SKILL.md"
        _write(dest, merged_content, force)
        written.append(dest)

    # Emit remaining individual skills
    for skill_dir in sorted(SKILLS_SRC.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name = skill_dir.name
        if name in exclude_skills or name in consumed:
            continue

        content = skill_md.read_text(encoding="utf-8")
        content = _apply_replacements(content, replacements)
        content = _humanize_unfilled_placeholders(content)

        dest = output / "skills" / name / "SKILL.md"
        _write(dest, content, force)
        written.append(dest)

    return written


# Template files from the parent directory to bundle in the plugin.
# Excludes __init__.py and directories (agents/, skills/, prompts/) which are
# handled separately.
TEMPLATE_EXTRAS: tuple[str, ...] = (
    "AGENTS.md",
    "builtin_agents.md",
    "operations.md",
    "workflows.md",
    "tools.md",
    "library_api.md",
    "skills.md",
    "agent_config.example.yaml",
)


def _copy_templates(
    output: Path,
    replacements: dict[str, str],
    force: bool,
) -> list[Path]:
    """Copy supplementary template files and prompts into templates/ in the plugin."""
    written: list[Path] = []
    dest_dir = output / "templates"

    # Copy top-level template markdown/yaml files
    for name in TEMPLATE_EXTRAS:
        src = TEMPLATES_DIR / name
        if not src.exists():
            continue
        content = src.read_text(encoding="utf-8")
        content = _apply_replacements(content, replacements)
        content = _humanize_unfilled_placeholders(content)
        dest = dest_dir / name
        _write(dest, content, force)
        written.append(dest)

    # Copy prompt modules
    if PROMPTS_SRC.exists():
        for p in sorted(PROMPTS_SRC.iterdir()):
            if p.suffix == ".md" and p.is_file():
                content = p.read_text(encoding="utf-8")
                content = _apply_replacements(content, replacements)
                content = _humanize_unfilled_placeholders(content)
                dest = dest_dir / "prompts" / p.name
                _write(dest, content, force)
                written.append(dest)

    return written


# ---------------------------------------------------------------------------
# Compact-marketplace consolidation
# ---------------------------------------------------------------------------

# Ordered map: (section title, source files).
# Part 1 = prompt modules (behavioural guidelines),
# Part 2 = configuration templates,
# Part 3 = reference / router docs.
_COMPACT_SECTIONS: list[tuple[str, str, list[str]]] = [
    # --- Part 1: Behavioral Guidelines ---
    ("Part 1: Behavioral Guidelines", "", []),
    ("Scientific Rigor Principles", "prompts", ["scientific_rigor.md"]),
    ("Analysis Workflow", "prompts", ["code_execution.md"]),
    ("Incremental Execution Principle", "prompts", ["incremental_execution.md"]),
    ("Reproducible Script Generation", "prompts", ["reproducible_script.md"]),
    ("Clarification & Follow-Up", "prompts", ["clarification.md"]),
    ("Communication Style", "prompts", ["communication_style.md"]),
    ("Thinking Out Loud", "prompts", ["thinking_out_loud.md"]),
    ("Output Directory", "prompts", ["output_dir.md"]),
    # --- Part 2: Configuration Templates ---
    ("Part 2: Configuration Templates", "", []),
    ("Operations", "root", ["operations.md"]),
    ("Workflows", "root", ["workflows.md"]),
    ("Tools Reference", "root", ["tools.md"]),
    ("Library API Reference", "root", ["library_api.md"]),
    ("Skills Overview", "root", ["skills.md"]),
    # --- Part 3: Reference Documentation ---
    ("Part 3: Reference Documentation", "", []),
    ("Template Router", "root", ["AGENTS.md"]),
    ("Built-in Agents", "root", ["builtin_agents.md"]),
    ("Agent Configuration YAML Example", "root", ["agent_config.example.yaml"]),
]


def _consolidate_templates(
    output: Path,
    replacements: dict[str, str],
    force: bool,
    skill_name: str = "configure-domain",
    name_prefix: str = "",
) -> list[Path]:
    """Consolidate all template files into a single ``sciagent-templates.md``.

    The file is placed inside the *configure-domain* skill directory so it
    ships as a bundled skill asset — compatible with plugin marketplaces that
    do not support tertiary template folders.

    Returns the list of files written (just the one consolidated file).
    """
    parts: list[str] = []
    section_num = 0

    for title, source_kind, filenames in _COMPACT_SECTIONS:
        # Part headers (no files — just a divider + heading)
        if not filenames:
            parts.append(f"\n---\n\n# {title}\n")
            continue

        section_num += 1
        section_bodies: list[str] = []
        for fname in filenames:
            if source_kind == "prompts":
                src = PROMPTS_SRC / fname
            else:
                src = TEMPLATES_DIR / fname
            if not src.exists():
                continue
            content = src.read_text(encoding="utf-8")
            # Strip any YAML frontmatter from prompts
            _, body = _split_frontmatter(content)
            body = body.strip() if body.strip() else content.strip()
            body = _apply_replacements(body, replacements)
            body = _humanize_unfilled_placeholders(body)
            section_bodies.append(body)

        if section_bodies:
            parts.append(f"\n## §{section_num} {title}\n\n" + "\n\n".join(section_bodies))

    consolidated = (
        "# SciAgent Templates — Consolidated Reference\n\n"
        "> This file bundles all SciAgent template content into a single\n"
        "> document for platforms that do not support separate template folders.\n"
        + "\n".join(parts)
        + "\n"
    )

    # Determine destination skill folder
    prefixed_skill = _prefixed(skill_name, name_prefix)
    dest = output / "skills" / prefixed_skill / "sciagent-templates.md"
    _write(dest, consolidated, force)
    return [dest]


def _build_readme(
    output: Path,
    version: str,
    agent_names: list[str],
    skill_names: list[str],
    name_prefix: str,
    force: bool,
) -> Path:
    """Generate a README.md for the plugin."""
    # Build agent description table with richer info
    agent_descriptions = {
        "analysis-planner": "Designs step-by-step analysis plans before any code runs",
        "code-reviewer": "Reviews scripts for correctness, reproducibility, and best practices",
        "coder": "Implements analysis code with built-in rigor enforcement",
        "coordinator": "Routes tasks to the right specialist agent",
        "data-qc": "Checks data quality — missing values, outliers, distributions, integrity",
        "docs-ingestor": "Ingests Python library docs into structured API references",
        "domain-assembler": "Configures SciAgent for your specific research domain",
        "report-writer": "Generates publication-quality reports with uncertainty quantification",
        "reviewer": "Reviews code and results for correctness, reproducibility, and scientific rigor",
        "rigor-reviewer": "Audits analysis for statistical validity and reproducibility",
    }
    agent_table = "\n".join(
        f"| `@{_prefixed(name, name_prefix)}` | {agent_descriptions.get(name, '')} |"
        for name in agent_names
    )
    skill_descriptions = {
        "scientific-rigor": "Mandatory rigor principles — data integrity, objectivity, uncertainty, reproducibility",
        "analysis-planner": "Step-by-step analysis planning with incremental validation",
        "data-qc": "Systematic data quality control checklist with severity-rated reporting",
        "rigor-reviewer": "8-point scientific rigor audit checklist",
        "report-writer": "Publication-quality report generation with uncertainty quantification",
        "code-reviewer": "7-point code review checklist for scientific scripts",
        "docs-ingestor": "Ingest Python library docs into structured API references",
        "configure-domain": "First-time domain setup — interviews you, discovers packages, fills templates",
        "update-domain": "Incrementally add packages, refine workflows, or extend domain content",
        "switch-domain": "Switch between configured research domains",
        "domain-expertise": "Domain-specific knowledge and terminology reference",
        "efel": "Electrophysiology Feature Extraction Library integration",
        "elephant": "Electrophysiology Analysis Toolkit integration",
        "neo": "Neural Ensemble Objects — multi-format electrophysiology I/O",
        "pyabf": "Axon Binary Format file loading and metadata",
    }
    skill_table = "\n".join(
        f"| `/{name}` | {skill_descriptions.get(name, name.replace('-', ' ').title())} |"
        for name in skill_names
    )

    n_agents = len(agent_names)
    n_skills = len(skill_names)

    readme = f"""\
# SciAgent — Scientific Analysis Agents for GitHub Copilot

> **{n_agents} specialized agents** and **{n_skills} skills** that bring scientific rigor
> to data analysis in VS Code. Plan experiments, check data quality, write
> reproducible code, audit results, and generate publication-ready reports —
> all with built-in guardrails against p-hacking, data fabrication, and
> irreproducible workflows.

**Version**: {version} | **License**: MIT | **Author**: [smestern](https://github.com/smestern)

## Why SciAgent?

Scientific coding is different from software engineering. A subtle off-by-one
in a loop isn't just a bug — it's a retracted paper. SciAgent enforces
scientific rigor through **5 technical layers** — code scanning, bounds
checking, data validation, rigor review, and reproducibility enforcement —
that implement **8 core principles**:

1. **Data Integrity** — never fabricate or fill gaps with synthetic data
2. **Objective Analysis** — reveal what data shows, not what you hope
3. **Sanity Checks** — validate inputs, flag impossible values
4. **Transparent Reporting** — report all results, even inconvenient ones
5. **Uncertainty Quantification** — confidence intervals, SEM, N for everything
6. **Reproducibility** — deterministic code, documented seeds, exact parameters
7. **Terminal Usage** — describe commands before running; prefer scripts over inline
8. **Rigor Warnings** — surface anomalous results to the user, never silently suppress

## Installation

### From Awesome Copilot Marketplace

```bash
copilot plugin marketplace add github/awesome-copilot
copilot plugin install sciagent@awesome-copilot
```

### Manual (VS Code)

Clone this repo and add to your VS Code settings:

```jsonc
// settings.json
"chat.plugins.paths": {{
    "/path/to/sciagent-plugin": true
}}
```

## Agents

| Agent | Description |
|-------|-------------|
{agent_table}

## Skills

| Skill | Description |
|-------|-------------|
{skill_table}

## Typical Workflow

```
You: @sciagent-coordinator I have calcium imaging data in traces.csv.
     Find responsive neurons and characterize their response profiles.

Coordinator → Analysis Planner → Data QC → Coder → Rigor Reviewer → Report Writer
```

Each agent hands off to the next, enforcing rigor at every step. The final
output is a structured report with figures, statistics, and reproducibility
metadata.

## Customization

SciAgent works out of the box for general scientific analysis. To specialize
for your research domain (e.g., electrophysiology, genomics, ecology), use
the `/configure-domain` skill which discovers relevant Python packages and
tailors agent behavior to your field.

## Framework

This plugin is generated from the [SciAgent framework](https://github.com/smestern/sciagent),
which also provides a Python SDK, CLI, and full-stack web interface for
building custom scientific analysis agents.

> **Build paths:** This plugin is generated by `scripts/build_plugin.py` into
> `build/plugin/sciagent/`. CI publishes the result to `dist/sciagent/` for
> distribution.

## License

MIT
"""
    path = output / "README.md"
    _write(path, readme, force)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a GitHub Copilot agent plugin from SciAgent templates.",
    )
    parser.add_argument(
        "-o", "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Plugin version string (default: read from pyproject.toml).",
    )
    parser.add_argument(
        "--name-prefix",
        default="sciagent",
        help="Prefix for agent names, e.g. 'sciagent' → 'sciagent-analysis-planner' (default: sciagent). Use '' for no prefix.",
    )
    parser.add_argument(
        "--no-prompts",
        action="store_true",
        help="Do not inline prompt modules into agent bodies.",
    )
    parser.add_argument(
        "--replacements-file",
        help="JSON or YAML map of placeholder replacements for REPLACE tags.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the build plan without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output directory.",
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        default="full",
        help="Build profile controlling agent/skill consolidation (default: full).",
    )
    parser.add_argument(
        "--format",
        choices=["standard", "compact-marketplace"],
        default="standard",
        dest="format",
        help=(
            "Output format. 'standard' (default) copies templates into templates/. "
            "'compact-marketplace' consolidates all templates and prompt modules "
            "into a single sciagent-templates.md bundled inside the "
            "configure-domain skill directory (for awesome-copilot marketplace)."
        ),
    )
    parser.add_argument(
        "--fullstack",
        action="store_true",
        help=(
            "Append fullstack tool overlay (execute_code, save_reproducible_script, "
            "OUTPUT_DIR, etc.) into agent bodies.  Default output is platform-agnostic."
        ),
    )
    return parser.parse_args()


def _run_dry(output: Path, version: str, agent_names: list[str], skill_names: list[str], name_prefix: str) -> None:
    print("[dry-run] SciAgent plugin build plan")
    print(f"  output:  {output}")
    print(f"  version: {version}")
    if name_prefix:
        print(f"  prefix:  {name_prefix}")
    print()
    print("  Files to write:")
    print(f"    {output / '.github' / 'plugin' / 'plugin.json'}")
    print(f"    {output / 'README.md'}")
    for name in agent_names:
        pname = _prefixed(name, name_prefix)
        print(f"    {output / 'agents' / (pname + '.md')}")
    for name in skill_names:
        print(f"    {output / 'skills' / name / 'SKILL.md'}")
    print(f"    --- templates ---")
    for name in TEMPLATE_EXTRAS:
        if (TEMPLATES_DIR / name).exists():
            print(f"    {output / 'templates' / name}")
    if PROMPTS_SRC.exists():
        for p in sorted(PROMPTS_SRC.iterdir()):
            if p.suffix == ".md" and p.is_file():
                print(f"    {output / 'templates' / 'prompts' / p.name}")
    print()
    n_templates = sum(1 for n in TEMPLATE_EXTRAS if (TEMPLATES_DIR / n).exists())
    n_prompts = sum(1 for p in PROMPTS_SRC.iterdir() if p.suffix == ".md" and p.is_file()) if PROMPTS_SRC.exists() else 0
    total = 2 + len(agent_names) + len(skill_names) + n_templates + n_prompts
    print(f"  Total: 2 + {len(agent_names)} agents + {len(skill_names)} skills"
          f" + {n_templates + n_prompts} templates = {total} files")


def main() -> None:
    args = _parse_args()

    if not TEMPLATES_DIR.exists():
        print(f"ERROR: templates directory not found: {TEMPLATES_DIR}", file=sys.stderr)
        sys.exit(1)

    project_meta = _read_pyproject()
    version = args.version or project_meta.get("version", "0.1.0")
    output = Path(args.output).resolve()

    profile = PROFILES[args.profile]
    agent_names, skill_names = _collect_names(profile)

    name_prefix = args.name_prefix

    if args.profile != "full":
        print(f"[profile: {args.profile}] {len(agent_names)} agents, {len(skill_names)} skills")

    if args.dry_run:
        _run_dry(output, version, agent_names, skill_names, name_prefix)
        return

    replacements = _read_replacements(
        Path(args.replacements_file) if args.replacements_file else None
    )

    # Clean output dir if --force
    if output.exists() and args.force:
        shutil.rmtree(output)

    try:
        plugin_json = _build_plugin_json(
            output, version, project_meta, agent_names, skill_names,
            name_prefix=name_prefix, force=args.force,
        )
        agent_files = _build_agents(
            output, replacements, include_prompts=not args.no_prompts,
            name_prefix=name_prefix, force=args.force, profile=profile,
            fullstack=args.fullstack,
        )
        skill_files = _build_skills(
            output, replacements, args.force, profile=profile,
        )

        # Post-process: rewrite handoffs and body text per profile
        handoff_rewrites = profile.get("handoff_rewrites", {})
        body_rewrites = profile.get("body_rewrites", {})
        if handoff_rewrites:
            _rewrite_handoffs(agent_files, handoff_rewrites, name_prefix)
        if body_rewrites:
            _apply_body_rewrites(agent_files, body_rewrites, name_prefix)
        _rewrite_routing_table(agent_files, profile, name_prefix, skill_names)

        template_files: list[Path] = []
        if args.format == "compact-marketplace":
            template_files = _consolidate_templates(
                output, replacements, args.force,
                name_prefix=name_prefix,
            )
        else:
            template_files = _copy_templates(output, replacements, args.force)
        readme = _build_readme(output, version, agent_names, skill_names, name_prefix, args.force)
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"SciAgent plugin built successfully → {output}")
    print(f"\n  {plugin_json.relative_to(output)}")
    print(f"  {readme.relative_to(output)}")
    for f in agent_files:
        print(f"  {f.relative_to(output)}")
    for f in skill_files:
        print(f"  {f.relative_to(output)}")
    if template_files:
        print("  --- templates ---")
        for f in template_files:
            print(f"  {f.relative_to(output)}")

    total = 2 + len(agent_files) + len(skill_files) + len(template_files)
    print(f"\nTotal: {total} files")
    print(
        f'\nTo install locally, add to VS Code settings.json:\n'
        f'  "chat.plugins.paths": {{\n'
        f'      "{output.as_posix()}": true\n'
        f'  }}'
    )


if __name__ == "__main__":
    main()
