#!/usr/bin/env python3
"""Convert an AgentConfig or YAML file to VS Code / Claude Code agent files.

Two input modes:

  From Python AgentConfig::

      python scripts/convert_to_agents.py \\
          --from-config examples.csv_analyst.config:CSV_CONFIG \\
          -o ./my_project

  From YAML config::

      python scripts/convert_to_agents.py \\
          --from-yaml templates/agent_config.example.yaml \\
          -o ./my_project

Options:

  --format    vscode | claude | both   (default: both)
  --include-defaults                   Bundle the 5 default agents alongside
  --skills                             Also generate SKILL.md files

Usage::

    python scripts/convert_to_agents.py --help
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Ensure the repo's src/ is importable when running as a script
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_config_from_python(spec: str):
    """Import ``module.path:ATTRIBUTE`` and return the AgentConfig."""
    if ":" not in spec:
        msg = (
            "ERROR: --from-config expects"
            f" 'module.path:ATTRIBUTE', got '{spec}'"
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    module_path, attr_name = spec.rsplit(":", 1)
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        print(
            f"ERROR: Cannot import '{module_path}': "
            f"{exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    config = getattr(mod, attr_name, None)
    if config is None:
        print(
            f"ERROR: Module '{module_path}' has no attribute '{attr_name}'",
            file=sys.stderr,
        )
        sys.exit(1)

    return config


def _load_config_from_yaml(path: str):
    """Read a YAML file and return (AgentConfig, extras_dict)."""
    try:
        import yaml
    except ImportError:
        print(
            "ERROR: PyYAML required for --from-yaml."
            " Install: pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)

    from sciagent.agents.converter import yaml_to_config

    yaml_path = Path(path)
    if not yaml_path.exists():
        print(f"ERROR: YAML file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    config = yaml_to_config(data)
    extras = {
        "domain_prompt": data.get("domain_prompt", ""),
        "tools_override": data.get("tools_override"),
    }
    return config, extras


def _copy_default_agents(output_dir: Path, fmt: str) -> None:
    """Copy the shipped default agent files into *output_dir*."""
    agents_src = REPO_ROOT / "templates" / "agents"
    if not agents_src.exists():
        print(
            "WARNING: templates/agents/ not found"
            " in repo root, skipping defaults",
            file=sys.stderr,
        )
        return

    import shutil

    if fmt in ("vscode", "both"):
        src = agents_src / ".github"
        if src.exists():
            dst = output_dir / ".github"
            if dst.exists():
                # Merge — don't clobber existing .github
                for sub in ("agents", "instructions"):
                    s = src / sub
                    d = dst / sub
                    if s.exists():
                        d.mkdir(parents=True, exist_ok=True)
                        for f in s.iterdir():
                            shutil.copy2(f, d / f.name)
            else:
                shutil.copytree(src, dst)

    if fmt in ("claude", "both"):
        src = agents_src / ".claude"
        if src.exists():
            dst = output_dir / ".claude"
            if dst.exists():
                d = dst / "agents"
                d.mkdir(parents=True, exist_ok=True)
                for f in (src / "agents").iterdir():
                    shutil.copy2(f, d / f.name)
            else:
                shutil.copytree(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert AgentConfig or YAML to"
            " VS Code / Claude Code agent files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-config",
        metavar="MODULE:ATTR",
        help=(
            "Python import path to an AgentConfig,"
            " e.g. 'my_module.config:MY_CONFIG'"
        ),
    )
    source.add_argument(
        "--from-yaml",
        metavar="PATH",
        help=(
            "Path to a YAML config file"
            " (see templates/agent_config.example.yaml)"
        ),
    )

    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["vscode", "claude", "both"],
        default="both",
        help="Which agent format(s) to generate (default: both)",
    )
    parser.add_argument(
        "--include-defaults",
        action="store_true",
        help="Also copy the 5 default sciagent agents into the output",
    )
    parser.add_argument(
        "--skills",
        action="store_true",
        help=(
            "Also generate SKILL.md files alongside agent files. "
            "When combined with --include-defaults, copies the 6 "
            "default skills as well."
        ),
    )

    args = parser.parse_args()

    from sciagent.agents.converter import agent_to_copilot_files

    output_dir = Path(args.output)
    domain_prompt = ""
    tools_vscode = None
    tools_claude = None

    if args.from_config:
        config = _load_config_from_python(args.from_config)
    else:
        config, extras = _load_config_from_yaml(args.from_yaml)
        domain_prompt = extras.get("domain_prompt", "")
        tools_vscode = extras.get("tools_override")

    result = agent_to_copilot_files(
        config,
        output_dir,
        domain_prompt=domain_prompt,
        tools_vscode=tools_vscode,
        tools_claude=tools_claude,
        fmt=args.format,
        skills=args.skills,
    )

    if args.include_defaults:
        _copy_default_agents(output_dir, args.format)
        print("  + Default agents copied")

        if args.skills:
            from sciagent.agents.converter import copy_default_skills

            copied = copy_default_skills(output_dir)
            print(f"  + {len(copied)} default skills copied")

    print(f"\nDone. Agent files written to: {result}")

    # Summary
    if args.format in ("vscode", "both"):
        vs = result / ".github" / "agents"
        print(f"  VS Code:  {vs / (config.name + '.agent.md')}")
    if args.format in ("claude", "both"):
        cl = result / ".claude" / "agents"
        print(f"  Claude:   {cl / (config.name + '.md')}")
    if args.skills:
        sk = result / ".github" / "skills" / config.name
        print(f"  Skill:    {sk / 'SKILL.md'}")
        if args.include_defaults:
            print(f"  Default skills: {result / '.github' / 'skills'}")


if __name__ == "__main__":
    main()
