#!/usr/bin/env python3
"""Install SciAgent markdown templates into Copilot-compatible locations.

This script materializes files from ``templates/`` into locations that VS Code
Copilot recognizes for custom instructions.

Layouts:
  - hybrid (default):
      * Creates a thin AGENTS.md router file with links
      * Installs modular ``*.instructions.md`` files
  - mono:
      * Creates a single AGENTS.md with merged template content

Targets:
  - workspace: install into a repository root (default: current directory)
  - user: install instructions into the active VS Code profile prompts folder

Examples::

    python scripts/install_templates.py --layout hybrid --target workspace
    python scripts/install_templates.py --layout mono --target workspace -o ./my_repo
    python scripts/install_templates.py --layout hybrid --target user
    python scripts/install_templates.py --target user --install-user-skills
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"


@dataclass(frozen=True)
class TemplateSpec:
    source_name: str
    instruction_name: str
    description: str
    apply_to: str | None = None


TEMPLATE_SPECS: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        source_name="operations.md",
        instruction_name="sciagent-operations.instructions.md",
        description="Scientific rigor and operating procedures for analyses.",
        apply_to="**",
    ),
    TemplateSpec(
        source_name="workflows.md",
        instruction_name="sciagent-workflows.instructions.md",
        description="Standard analysis workflows and sequencing guidance.",
    ),
    TemplateSpec(
        source_name="tools.md",
        instruction_name="sciagent-tools.instructions.md",
        description="Tool contracts, parameters, and return schema guidance.",
    ),
    TemplateSpec(
        source_name="library_api.md",
        instruction_name="sciagent-library-api.instructions.md",
        description="Primary domain library API conventions and pitfalls.",
    ),
    TemplateSpec(
        source_name="skills.md",
        instruction_name="sciagent-skills.instructions.md",
        description="Skill guidance, trigger phrases, and capability definitions.",
    ),
)


REPLACE_PATTERN = re.compile(
    r"<!--\s*REPLACE:\s*([a-zA-Z0-9_]+)\s*[—-].*?-->",
    flags=re.DOTALL,
)


def _detect_user_prompts_dir() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is not set; cannot determine VS Code profile path")
        return Path(appdata) / "Code" / "User" / "prompts"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "prompts"

    return Path.home() / ".config" / "Code" / "User" / "prompts"


def _default_user_skills_dir() -> Path:
    return Path.home() / ".copilot" / "skills"


def _read_replacements(path: Path | None) -> dict[str, str]:
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
    if not replacements:
        return text

    def replace_match(match: re.Match[str]) -> str:
        key = match.group(1)
        return replacements.get(key, match.group(0))

    return REPLACE_PATTERN.sub(replace_match, text)


def _with_frontmatter(body: str, name: str, description: str, apply_to: str | None) -> str:
    frontmatter_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if apply_to:
        frontmatter_lines.append(f"applyTo: {apply_to}")
    frontmatter_lines.append("---")
    return "\n".join(frontmatter_lines) + "\n\n" + body.lstrip()


def _extract_rigor_section(operations_text: str) -> str:
    start = operations_text.find("## ⚠️ SCIENTIFIC RIGOR POLICY (MANDATORY)")
    if start == -1:
        return ""

    next_header = operations_text.find("\n## ", start + 1)
    if next_header == -1:
        return operations_text[start:].strip()
    return operations_text[start:next_header].strip()


def _agents_router_content(instruction_paths: Iterable[str], rigor_excerpt: str) -> str:
    links = "\n".join(f"- [{p}]({p})" for p in instruction_paths)
    rigor_block = rigor_excerpt or "## Scientific Rigor\nFollow rigorous, transparent analysis practices."
    return f"""# AGENTS

SciAgent operating guidance for coding agents in this repository.

{rigor_block}

## Linked Instructions

Use the following instruction files for domain and workflow details:

{links}

When files appear relevant, open and apply those instructions before implementing changes.
"""


def _mono_agents_content(rendered_templates: list[tuple[str, str]]) -> str:
    sections: list[str] = [
        "# AGENTS",
        "",
        "Merged SciAgent guidance generated from templates.",
        "",
    ]

    for source_name, body in rendered_templates:
        title = source_name.replace(".md", "").replace("_", " ").title()
        sections.append(f"## Source: {title}")
        sections.append("")
        sections.append(body.strip())
        sections.append("")

    return "\n".join(sections).rstrip() + "\n"


def _write_text(path: Path, content: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")
    path.write_text(content, encoding="utf-8")


def _validate_links(agents_path: Path, linked_paths: Iterable[Path]) -> list[str]:
    missing = [str(path) for path in linked_paths if not path.exists()]
    if agents_path.exists() and missing:
        return missing
    return []


def _install_workspace_hybrid(
    workspace_root: Path,
    replacements: dict[str, str],
    force: bool,
) -> list[Path]:
    written: list[Path] = []
    instructions_dir = workspace_root / ".github" / "instructions"
    instruction_rel_paths: list[str] = []
    linked_abs_paths: list[Path] = []

    operations_text = (TEMPLATES_DIR / "operations.md").read_text(encoding="utf-8")
    rendered_operations = _apply_replacements(operations_text, replacements)
    rigor_excerpt = _extract_rigor_section(rendered_operations)

    for spec in TEMPLATE_SPECS:
        source_path = TEMPLATES_DIR / spec.source_name
        content = _apply_replacements(source_path.read_text(encoding="utf-8"), replacements)
        content = _with_frontmatter(
            body=content,
            name=spec.instruction_name.replace(".instructions.md", ""),
            description=spec.description,
            apply_to=spec.apply_to,
        )
        target_path = instructions_dir / spec.instruction_name
        _write_text(target_path, content, force=force)
        written.append(target_path)
        rel = f".github/instructions/{spec.instruction_name}"
        instruction_rel_paths.append(rel)
        linked_abs_paths.append(target_path)

    agents_path = workspace_root / "AGENTS.md"
    agents_content = _agents_router_content(
        instruction_paths=instruction_rel_paths,
        rigor_excerpt=rigor_excerpt,
    )
    _write_text(agents_path, agents_content, force=force)
    written.append(agents_path)

    copilot_path = workspace_root / ".github" / "copilot-instructions.md"
    copilot_content = (
        "# SciAgent Core Instructions\n\n"
        "Use AGENTS.md as the primary router for SciAgent conventions.\n\n"
        "- [AGENTS.md](../AGENTS.md)\n"
    )
    _write_text(copilot_path, copilot_content, force=force)
    written.append(copilot_path)

    missing = _validate_links(agents_path, linked_abs_paths)
    if missing:
        print("WARNING: AGENTS.md contains missing links:")
        for path in missing:
            print(f"  - {path}")

    return written


def _install_workspace_mono(
    workspace_root: Path,
    replacements: dict[str, str],
    force: bool,
) -> list[Path]:
    rendered: list[tuple[str, str]] = []
    for source in (
        "operations.md",
        "workflows.md",
        "tools.md",
        "library_api.md",
        "skills.md",
    ):
        source_path = TEMPLATES_DIR / source
        text = _apply_replacements(source_path.read_text(encoding="utf-8"), replacements)
        rendered.append((source, text))

    agents_path = workspace_root / "AGENTS.md"
    _write_text(agents_path, _mono_agents_content(rendered), force=force)

    copilot_path = workspace_root / ".github" / "copilot-instructions.md"
    copilot_content = (
        "# SciAgent Core Instructions\n\n"
        "Use AGENTS.md as the canonical merged instruction source.\n\n"
        "- [AGENTS.md](../AGENTS.md)\n"
    )
    _write_text(copilot_path, copilot_content, force=force)

    return [agents_path, copilot_path]


def _install_user_instructions(
    prompts_dir: Path,
    replacements: dict[str, str],
    layout: str,
    force: bool,
) -> list[Path]:
    prompts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if layout == "mono":
        rendered: list[tuple[str, str]] = []
        for source in (
            "operations.md",
            "workflows.md",
            "tools.md",
            "library_api.md",
            "skills.md",
        ):
            text = _apply_replacements((TEMPLATES_DIR / source).read_text(encoding="utf-8"), replacements)
            rendered.append((source, text))

        body = _mono_agents_content(rendered)
        instruction_path = prompts_dir / "sciagent.instructions.md"
        content = _with_frontmatter(
            body=body,
            name="sciagent",
            description="Merged SciAgent guidance installed at user scope.",
            apply_to="**",
        )
        _write_text(instruction_path, content, force=force)
        written.append(instruction_path)
        return written

    for spec in TEMPLATE_SPECS:
        text = _apply_replacements((TEMPLATES_DIR / spec.source_name).read_text(encoding="utf-8"), replacements)
        content = _with_frontmatter(
            body=text,
            name=spec.instruction_name.replace(".instructions.md", ""),
            description=spec.description,
            apply_to=spec.apply_to,
        )
        target = prompts_dir / spec.instruction_name
        _write_text(target, content, force=force)
        written.append(target)

    return written


def _install_user_skills(skills_dir: Path, force: bool) -> list[Path]:
    source_skills_dir = TEMPLATES_DIR / "skills"
    if not source_skills_dir.exists():
        raise FileNotFoundError(f"Skills templates not found: {source_skills_dir}")

    copied: list[Path] = []
    skills_dir.mkdir(parents=True, exist_ok=True)

    for child in source_skills_dir.iterdir():
        if not child.is_dir():
            continue

        destination = skills_dir / child.name
        if destination.exists():
            if not force:
                raise FileExistsError(
                    f"Refusing to overwrite existing skill directory without --force: {destination}"
                )
            shutil.rmtree(destination)

        shutil.copytree(child, destination)
        copied.append(destination)

    return copied


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install SciAgent templates into Copilot-recognized instruction locations.",
    )
    parser.add_argument(
        "--layout",
        choices=["hybrid", "mono"],
        default="hybrid",
        help="Install modular instructions + AGENTS router (hybrid) or one merged AGENTS/instruction file (mono).",
    )
    parser.add_argument(
        "--target",
        choices=["workspace", "user"],
        default="workspace",
        help="Install into the current workspace root or user-level VS Code profile instructions folder.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Workspace root path when --target workspace (default: current directory).",
    )
    parser.add_argument(
        "--user-prompts-dir",
        help="Override user prompts directory (default auto-detected VS Code profile prompts folder).",
    )
    parser.add_argument(
        "--replacements-file",
        help="JSON or YAML map of placeholder replacements for REPLACE tags.",
    )
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Inline replacement for a REPLACE placeholder key (repeatable).",
    )
    parser.add_argument(
        "--install-user-skills",
        action="store_true",
        help="Also copy templates/skills/* to ~/.copilot/skills (or --user-skills-dir).",
    )
    parser.add_argument(
        "--user-skills-dir",
        help="Override user skills directory (default: ~/.copilot/skills).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files/directories.",
    )
    return parser.parse_args()


def _parse_inline_replacements(values: list[str]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --replace value '{item}'. Expected KEY=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Invalid --replace value with empty key")
        replacements[key] = value
    return replacements


def _run_dry(args: argparse.Namespace, replacements: dict[str, str]) -> None:
    print("[dry-run] SciAgent template installation plan")
    print(f"  layout: {args.layout}")
    print(f"  target: {args.target}")
    print(f"  replacements: {len(replacements)} keys")

    if args.target == "workspace":
        root = Path(args.output).resolve()
        if args.layout == "hybrid":
            print(f"  - write: {root / 'AGENTS.md'}")
            print(f"  - write: {root / '.github' / 'copilot-instructions.md'}")
            for spec in TEMPLATE_SPECS:
                print(f"  - write: {root / '.github' / 'instructions' / spec.instruction_name}")
        else:
            print(f"  - write: {root / 'AGENTS.md'}")
            print(f"  - write: {root / '.github' / 'copilot-instructions.md'}")
    else:
        prompts_dir = Path(args.user_prompts_dir).resolve() if args.user_prompts_dir else _detect_user_prompts_dir()
        print(f"  - write into user prompts dir: {prompts_dir}")
        if args.layout == "mono":
            print(f"  - write: {prompts_dir / 'sciagent.instructions.md'}")
        else:
            for spec in TEMPLATE_SPECS:
                print(f"  - write: {prompts_dir / spec.instruction_name}")

    if args.install_user_skills:
        skills_dir = Path(args.user_skills_dir).resolve() if args.user_skills_dir else _default_user_skills_dir()
        print(f"  - copy skills to: {skills_dir}")


def main() -> None:
    args = _parse_args()

    if not TEMPLATES_DIR.exists():
        print(f"ERROR: templates directory not found: {TEMPLATES_DIR}", file=sys.stderr)
        sys.exit(1)

    replacements = _read_replacements(Path(args.replacements_file)) if args.replacements_file else {}
    replacements.update(_parse_inline_replacements(args.replace))

    if args.dry_run:
        _run_dry(args, replacements)
        return

    written: list[Path] = []
    copied_skills: list[Path] = []

    try:
        if args.target == "workspace":
            workspace_root = Path(args.output).resolve()
            if args.layout == "hybrid":
                written = _install_workspace_hybrid(
                    workspace_root=workspace_root,
                    replacements=replacements,
                    force=args.force,
                )
            else:
                written = _install_workspace_mono(
                    workspace_root=workspace_root,
                    replacements=replacements,
                    force=args.force,
                )
        else:
            prompts_dir = (
                Path(args.user_prompts_dir).resolve()
                if args.user_prompts_dir
                else _detect_user_prompts_dir()
            )
            written = _install_user_instructions(
                prompts_dir=prompts_dir,
                replacements=replacements,
                layout=args.layout,
                force=args.force,
            )

        if args.install_user_skills:
            skills_dir = (
                Path(args.user_skills_dir).resolve()
                if args.user_skills_dir
                else _default_user_skills_dir()
            )
            copied_skills = _install_user_skills(skills_dir=skills_dir, force=args.force)

    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Installed SciAgent templates successfully.")
    if written:
        print("\nWritten files:")
        for path in written:
            print(f"  - {path}")
    if copied_skills:
        print("\nCopied skills:")
        for path in copied_skills:
            print(f"  - {path}")

    if args.target == "workspace":
        print(
            "\nTip: In VS Code Chat, open Configure Chat > Diagnostics to confirm"
            " AGENTS.md and instruction files are loaded."
        )


if __name__ == "__main__":
    main()
