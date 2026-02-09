"""
CSV Analyst agent — subclasses ``BaseScientificAgent``.

This is the core of the example: a ~50-line agent definition that
inherits the entire scientific coding framework for free.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from sciagent.base_agent import BaseScientificAgent
from sciagent.prompts.base_messages import build_system_message
from sciagent.tools.code_tools import execute_code, validate_code

from .config import CSV_CONFIG

# ---------------------------------------------------------------------------
# Domain-specific system prompt section
# ---------------------------------------------------------------------------
CSV_INSTRUCTIONS = """
## CSV Analysis Specialist

You help users explore, clean, and analyse tabular CSV data.

### Guidelines
- Always start by loading the file with ``pandas.read_csv()`` and showing
  ``df.shape`` and ``df.dtypes`` so the user knows what they're working with.
- Prefer vectorised pandas/numpy operations over loops.
- When the user asks for a plot, use **matplotlib** or **seaborn** and always
  add axis labels and a title.
- Never modify the original file on disk; work on in-memory copies.
"""


class CSVAnalyst(BaseScientificAgent):
    """Minimal scientific agent for CSV exploration."""

    def __init__(self):
        super().__init__(CSV_CONFIG)

    # -- Required override ---------------------------------------------------
    def _load_tools(self) -> List[Dict[str, Any]]:
        return [
            self._create_tool(
                name="execute_code",
                description=(
                    "Run Python code for CSV analysis. pandas, numpy, "
                    "matplotlib, and seaborn are available."
                ),
                parameters={
                    "code": {
                        "type": "string",
                        "description": "Python code to execute",
                    }
                },
                required=["code"],
                func=execute_code,
            ),
            self._create_tool(
                name="validate_code",
                description="Check Python code for syntax errors before running.",
                parameters={
                    "code": {
                        "type": "string",
                        "description": "Python code to validate",
                    }
                },
                required=["code"],
                func=validate_code,
            ),
        ]

    # -- Optional overrides --------------------------------------------------
    def _get_system_message(self) -> str:
        return build_system_message(CSV_INSTRUCTIONS)

    def _get_execution_environment(self) -> Dict[str, Any]:
        """Pre-import pandas & seaborn into the sandbox."""
        env: Dict[str, Any] = {}
        try:
            import pandas as pd
            import seaborn as sns

            env["pd"] = pd
            env["sns"] = sns
        except ImportError:
            pass
        return env


# ---------------------------------------------------------------------------
# Factory (matches the pattern expected by sciagent's web & CLI helpers)
# ---------------------------------------------------------------------------
def create_agent() -> CSVAnalyst:
    return CSVAnalyst()
