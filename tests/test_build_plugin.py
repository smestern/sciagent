"""Tests for scripts/build_plugin.py — banner injection in particular.

Guards against a regression where the AUTO-GENERATED banner was prepended
above the YAML frontmatter, causing every generated SKILL.md / agent file
to fail line-1 ``---`` frontmatter parsing (Copilot, Claude Code, and the
script's own ``_split_frontmatter``).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_plugin.py"


def _load_build_plugin():
    spec = importlib.util.spec_from_file_location("build_plugin", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_plugin"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


bp = _load_build_plugin()


def test_banner_inject_preserves_line1_dashes() -> None:
    """File with frontmatter must still start with '---' after banner inject."""
    content = "---\nname: foo\ndescription: bar\n---\n\nBody.\n"
    result = bp._inject_generated_banner(content, "templates/skills/foo/SKILL.md")
    assert result.startswith("---\n"), (
        "Banner injection broke the line-1 frontmatter marker; "
        "Copilot / Claude / _split_frontmatter will fail to parse this file."
    )


def test_banner_inject_keeps_frontmatter_parseable() -> None:
    """The script's own _split_frontmatter must still find frontmatter."""
    content = "---\nname: foo\ndescription: bar\n---\n\nBody.\n"
    result = bp._inject_generated_banner(content, "templates/skills/foo/SKILL.md")
    fm, body = bp._split_frontmatter(result)
    assert fm, "frontmatter was lost after banner injection"
    assert "name: foo" in fm
    assert "description: bar" in fm
    assert "AUTO-GENERATED" in fm  # banner ended up inside frontmatter (as YAML comments)
    assert body.strip() == "Body."


def test_banner_inject_no_frontmatter_falls_back_to_html() -> None:
    """Files without frontmatter get an HTML-comment banner prepended."""
    content = "# Plain Markdown\n\nNo frontmatter here.\n"
    result = bp._inject_generated_banner(content, "templates/foo.md")
    assert result.startswith("<!--\n")
    assert "AUTO-GENERATED" in result
    assert result.endswith(content)


def test_banner_inject_yaml_comment_lines_start_with_hash() -> None:
    """Every banner line inside frontmatter must be a YAML comment (# ...)."""
    content = "---\nname: foo\n---\nBody\n"
    result = bp._inject_generated_banner(content, "src.md")
    # Extract lines between the two ---
    lines = result.split("\n")
    assert lines[0] == "---"
    # Walk until we hit name: or the closing ---
    for line in lines[1:]:
        if line.startswith("name:") or line == "---":
            break
        assert line == "" or line.startswith("#"), (
            f"Non-comment line inside frontmatter would corrupt YAML: {line!r}"
        )


def test_generated_dist_files_have_parseable_frontmatter() -> None:
    """Every generated SKILL.md / agent .md in dist/sciagent/ must parse.

    This is the end-to-end guard: it walks the committed dist artifact and
    asserts that line 1 is ``---`` and frontmatter is recoverable for every
    skill and agent file.
    """
    dist = REPO_ROOT / "dist" / "sciagent"
    if not dist.exists():
        pytest.skip("dist/sciagent/ not present (run build first)")

    targets = list((dist / "skills").glob("*/SKILL.md")) + list(
        (dist / "agents").glob("*.md")
    )
    assert targets, "no generated files found under dist/sciagent/"

    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), (
            f"{path.relative_to(REPO_ROOT)} does not start with '---'; "
            "plugin loaders will reject it."
        )
        fm, _ = bp._split_frontmatter(text)
        assert fm, f"frontmatter missing or unparseable in {path.relative_to(REPO_ROOT)}"
        # Sanity: required identity fields survive
        assert "name:" in fm, f"name: missing in frontmatter of {path}"
