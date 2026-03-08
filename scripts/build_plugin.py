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

# Reference to shared rigor instructions that each agent links to.
# We replace this link with the inlined content.
RIGOR_LINK_PATTERN = re.compile(
    r"Follow the \[shared scientific rigor principles\]"
    r"\([^)]*sciagent-rigor\.instructions\.md\)\.",
)

# Which prompt modules to append to each agent.
# Keys are agent stems (without extension), values are prompt filenames.
AGENT_PROMPT_MAP: dict[str, list[str]] = {
    "coordinator": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
    "analysis-planner": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
    "data-qc": [
        "scientific_rigor.md",
        "communication_style.md",
        "code_execution.md",
        "incremental_execution.md",
        "clarification.md",
    ],
    "rigor-reviewer": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
    "report-writer": [
        "scientific_rigor.md",
        "communication_style.md",
        "reproducible_script.md",
        "clarification.md",
    ],
    "code-reviewer": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
    "docs-ingestor": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
    "sciagent-coder": [
        "scientific_rigor.md",
        "communication_style.md",
        "code_execution.md",
        "incremental_execution.md",
        "reproducible_script.md",
        "clarification.md",
    ],
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


def _build_plugin_json(
    output: Path,
    version: str,
    project_meta: dict[str, Any],
    agent_names: list[str],
    skill_names: list[str],
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
        "agents": ["./agents"],
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
) -> list[Path]:
    """Compile agent .agent.md files → agents/<name>.md with inlined instructions."""
    rigor_text = ""
    rigor_path = INSTRUCTIONS_SRC / "sciagent-rigor.instructions.md"
    if rigor_path.exists():
        rigor_text = rigor_path.read_text(encoding="utf-8").strip()

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

    for src_file in sorted(AGENTS_SRC.glob("*.agent.md")):
        raw = src_file.read_text(encoding="utf-8")
        raw = _apply_replacements(raw, replacements)

        fm_text, body = _split_frontmatter(raw)

        # Replace the rigor-instructions link with inlined content
        if rigor_text:
            replacement_block = (
                "### Shared Scientific Rigor Principles\n\n" + rigor_text
            )
            body = RIGOR_LINK_PATTERN.sub(replacement_block, body)

        # Append relevant prompt modules
        agent_stem = src_file.stem.replace(".agent", "")
        if include_prompts and agent_stem in AGENT_PROMPT_MAP:
            appendices: list[str] = []
            for prompt_name in AGENT_PROMPT_MAP[agent_stem]:
                if prompt_name in prompt_cache:
                    appendices.append(prompt_cache[prompt_name])
            if appendices:
                body = body.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(appendices) + "\n"

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
) -> list[Path]:
    """Copy skill directories, applying replacements to SKILL.md files."""
    written: list[Path] = []
    if not SKILLS_SRC.exists():
        print(f"WARNING: skills source not found: {SKILLS_SRC}", file=sys.stderr)
        return written

    for skill_dir in sorted(SKILLS_SRC.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8")
        content = _apply_replacements(content, replacements)

        dest = output / "skills" / skill_dir.name / "SKILL.md"
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
        dest = dest_dir / name
        _write(dest, content, force)
        written.append(dest)

    # Copy prompt modules
    if PROMPTS_SRC.exists():
        for p in sorted(PROMPTS_SRC.iterdir()):
            if p.suffix == ".md" and p.is_file():
                content = p.read_text(encoding="utf-8")
                content = _apply_replacements(content, replacements)
                dest = dest_dir / "prompts" / p.name
                _write(dest, content, force)
                written.append(dest)

    return written


def _build_readme(
    output: Path,
    version: str,
    agent_names: list[str],
    skill_names: list[str],
    name_prefix: str,
    force: bool,
) -> Path:
    """Generate a README.md for the plugin."""
    agent_table = "\n".join(
        f"| {_prefixed(name, name_prefix)} | `@{_prefixed(name, name_prefix)}` |"
        for name in agent_names
    )
    skill_table = "\n".join(
        f"| {name} | `/{name}` |"
        for name in skill_names
    )

    readme = f"""\
# SciAgent — Copilot Agent Plugin

Scientific analysis agents with built-in rigor enforcement for GitHub Copilot.

**Version**: {version}

## Installation

### Local (development)

Clone or download this plugin directory, then add it to your VS Code settings:

```jsonc
// settings.json
"chat.plugins.paths": {{
    "/path/to/sciagent": true
}}
```

### From marketplace

If published to a plugin marketplace repository, install via the Extensions
sidebar → Agent Plugins view, or search `@agentPlugins sciagent`.

## Agents

| Agent | Invocation |
|-------|------------|
{agent_table}

## Skills

| Skill | Slash Command |
|-------|---------------|
{skill_table}

## What's Included

- **6 specialized agents** for scientific analysis workflows: planning,
  data QC, code review, rigor auditing, report writing, and documentation
  ingestion.
- **7 skills** providing on-demand expertise: scientific rigor enforcement,
  analysis planning, data QC checklists, rigor review, report templates,
  code review, and library documentation ingestion.
- **Built-in scientific rigor principles** inlined into every agent —
  data integrity, objective analysis, sanity checks, transparent reporting,
  uncertainty quantification, and reproducibility.

## Source

This plugin is generated from the [SciAgent](https://github.com/smestern/sciagent)
framework templates.

## License

MIT
"""
    path = output / "README.md"
    _write(path, readme, force)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _collect_names() -> tuple[list[str], list[str]]:
    """Return sorted lists of agent stems and skill directory names."""
    agent_names: list[str] = []
    if AGENTS_SRC.exists():
        for f in sorted(AGENTS_SRC.glob("*.agent.md")):
            agent_names.append(f.stem.replace(".agent", ""))

    skill_names: list[str] = []
    if SKILLS_SRC.exists():
        for d in sorted(SKILLS_SRC.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                skill_names.append(d.name)

    return agent_names, skill_names


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

    agent_names, skill_names = _collect_names()

    name_prefix = args.name_prefix

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
            output, version, project_meta, agent_names, skill_names, args.force,
        )
        agent_files = _build_agents(
            output, replacements, include_prompts=not args.no_prompts,
            name_prefix=name_prefix, force=args.force,
        )
        skill_files = _build_skills(output, replacements, args.force)
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
