"""
CodeScanner — regex-based code scanner for scientific rigor enforcement.

Provides a default set of forbidden and warning patterns, plus extension
methods for domain-specific additions.
"""

from __future__ import annotations

import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ── Default patterns ────────────────────────────────────────────────────

DEFAULT_FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
    # Synthetic data generation
    (
        r"np\.random\.(rand|randn|random|uniform|normal|choice)\s*\(",
        "RIGOR VIOLATION: Random/synthetic data generation detected. "
        "Use real experimental data only.",
    ),
    (
        r"random\.(random|uniform|gauss|choice)\s*\(",
        "RIGOR VIOLATION: Random data generation detected. "
        "Use real experimental data only.",
    ),
    (
        r"fake|dummy|synthetic|simulated",
        "RIGOR VIOLATION: Code references fake/synthetic data. "
        "Use real experimental data only.",
    ),
    # Result manipulation
    (
        r"if.*p.?value.*[<>].*0\.05.*:.*=",
        "RIGOR VIOLATION: Conditional result modification based on p-value detected.",
    ),
    (
        r"result\s*=\s*(expected|hypothesis|target)",
        "RIGOR VIOLATION: Result forced to match expected/hypothesis value.",
    ),
    (
        r"#.*hack|#.*fudge|#.*fake",
        "RIGOR VIOLATION: Code contains suspicious comments suggesting data manipulation.",
    ),
]

DEFAULT_WARNING_PATTERNS: List[Tuple[str, str]] = [
    (
        r"np\.random\.seed",
        "Random seed set — ensure this is for reproducibility, not cherry-picking.",
    ),
    (
        r"outlier.*remove|remove.*outlier",
        "Outlier removal detected — document criteria and report how many removed.",
    ),
    (
        r"exclude|skip|ignore",
        "Data exclusion detected — document criteria and report what was excluded.",
    ),
]


class CodeScanner:
    """Scan code for scientific-rigor violations.

    The scanner ships with a default set of forbidden/warning patterns
    that cover the most common scientific integrity issues.  Domain-specific
    agents can extend the lists via :meth:`add_forbidden` and
    :meth:`add_warning`.

    Example::

        scanner = CodeScanner()
        scanner.add_forbidden(
            r"find_peaks\\s*\\(\\s*voltage",
            "Use detect_spikes tool instead of scipy find_peaks on voltage.",
        )
        result = scanner.check(user_code)
        if not result["passed"]:
            raise RuntimeError(result["violations"])
    """

    def __init__(self) -> None:
        self._forbidden: List[Tuple[str, str]] = list(DEFAULT_FORBIDDEN_PATTERNS)
        self._warnings: List[Tuple[str, str]] = list(DEFAULT_WARNING_PATTERNS)

    # -- extension API --------------------------------------------------------

    def add_forbidden(self, pattern: str, message: str) -> None:
        """Add a regex pattern that *blocks* code execution."""
        self._forbidden.append((pattern, message))

    def add_warning(self, pattern: str, message: str) -> None:
        """Add a regex pattern that produces a *warning* but allows execution."""
        self._warnings.append((pattern, message))

    def add_forbidden_batch(self, patterns: List[Tuple[str, str]]) -> None:
        """Add multiple forbidden patterns at once."""
        self._forbidden.extend(patterns)

    def add_warning_batch(self, patterns: List[Tuple[str, str]]) -> None:
        """Add multiple warning patterns at once."""
        self._warnings.extend(patterns)

    # -- scanning -------------------------------------------------------------

    def check(self, code: str) -> Dict[str, Any]:
        """Scan *code* for rigor violations and warnings.

        Returns:
            Dict with ``passed`` (bool), ``violations`` (list[str]),
            and ``warnings`` (list[str]).
        """
        violations: List[str] = []
        warnings: List[str] = []

        for pattern, message in self._forbidden:
            if re.search(pattern, code, re.IGNORECASE):
                violations.append(message)

        for pattern, message in self._warnings:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(message)

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
        }
