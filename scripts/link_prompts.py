#!/usr/bin/env python3
"""Re-create symlinks from templates/prompts/ → source .md files.

Symlinks make the relationship explicit and are visible in ``git status``.
However, ``git clone`` may not preserve symlinks on Windows unless
``core.symlinks = true`` is set.  Run this script after a fresh clone
(or whenever the links break) to restore them.

On Windows this requires either **Developer Mode** or an elevated
(Administrator) terminal.

Usage::

    python scripts/link_prompts.py        # Windows / Linux / macOS
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mapping: link name → relative path from templates/prompts/ to the source file
LINKS: dict[str, str] = {
    "scientific_rigor.md":        os.path.join("..", "..", "src", "sciagent", "prompts", "scientific_rigor.md"),
    "code_execution.md":          os.path.join("..", "..", "src", "sciagent", "prompts", "code_execution.md"),
    "output_dir.md":              os.path.join("..", "..", "src", "sciagent", "prompts", "output_dir.md"),
    "reproducible_script.md":     os.path.join("..", "..", "src", "sciagent", "prompts", "reproducible_script.md"),
    "thinking_out_loud.md":       os.path.join("..", "..", "src", "sciagent", "prompts", "thinking_out_loud.md"),
    "communication_style.md":     os.path.join("..", "..", "src", "sciagent", "prompts", "communication_style.md"),
    "incremental_execution.md":   os.path.join("..", "..", "src", "sciagent", "prompts", "incremental_execution.md"),
    "wizard_expertise.md":        os.path.join("..", "..", "src", "sciagent_wizard", "prompts", "wizard_expertise.md"),
    "public_wizard_expertise.md": os.path.join("..", "..", "src", "sciagent_wizard", "prompts", "public_wizard_expertise.md"),
}

# Absolute paths to the actual source files (for validation)
SOURCES: dict[str, str] = {
    "scientific_rigor.md":        "src/sciagent/prompts/scientific_rigor.md",
    "code_execution.md":          "src/sciagent/prompts/code_execution.md",
    "output_dir.md":              "src/sciagent/prompts/output_dir.md",
    "reproducible_script.md":     "src/sciagent/prompts/reproducible_script.md",
    "thinking_out_loud.md":       "src/sciagent/prompts/thinking_out_loud.md",
    "communication_style.md":     "src/sciagent/prompts/communication_style.md",
    "incremental_execution.md":   "src/sciagent/prompts/incremental_execution.md",
    "wizard_expertise.md":        "src/sciagent_wizard/prompts/wizard_expertise.md",
    "public_wizard_expertise.md": "src/sciagent_wizard/prompts/public_wizard_expertise.md",
}


def main() -> None:
    dest_dir = REPO_ROOT / "templates" / "prompts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for name, rel_target in LINKS.items():
        src_abs = REPO_ROOT / SOURCES[name]
        dest = dest_dir / name

        if not src_abs.exists():
            print(f"  SKIP  {name}  (source missing: {SOURCES[name]})")
            continue

        # Check if already a valid symlink pointing to the right place
        if dest.is_symlink():
            if dest.resolve() == src_abs.resolve():
                print(f"  OK    {name}  (already linked)")
                continue
            dest.unlink()
        elif dest.exists():
            dest.unlink()

        os.symlink(rel_target, str(dest))
        print(f"  LINK  {name}  → {rel_target}")

    print("\nDone.")


if __name__ == "__main__":
    main()
