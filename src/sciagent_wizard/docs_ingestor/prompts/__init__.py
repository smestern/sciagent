"""Prompt loader for the docs ingestor."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent

_INGESTOR_EXPERTISE_PATH = _PROMPTS_DIR / "ingestor_expertise.md"


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


INGESTOR_EXPERTISE: str = _load(_INGESTOR_EXPERTISE_PATH)

__all__ = ["INGESTOR_EXPERTISE"]
