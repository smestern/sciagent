"""
CodeScanner — regex-based code scanner for scientific rigor enforcement.

Provides a default set of forbidden and warning patterns, plus extension
methods for domain-specific additions.  Patterns carry a ``Severity``
level and the scanner's behaviour is governed by a ``RigorLevel``.
"""

from __future__ import annotations

import enum
import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


# ── Enums ───────────────────────────────────────────────────────────────


class Severity(enum.Enum):
    """How serious a pattern match is.

    ``CRITICAL`` — hard-blocks execution in STANDARD and STRICT modes.
    ``WARNING``  — requests user confirmation in STANDARD mode.
    """

    CRITICAL = "critical"
    WARNING = "warning"


class RigorLevel(enum.Enum):
    """User-configurable enforcement level for the code scanner.

    ``STRICT``   — *all* pattern matches (CRITICAL + WARNING) hard-block.
    ``STANDARD`` — CRITICAL patterns hard-block; WARNING patterns require
                   user confirmation before execution proceeds.
    ``RELAXED``  — CRITICAL patterns require confirmation; WARNING patterns
                   are informational only.
    ``BYPASS``   — scanner is disabled entirely (AST security gate in
                   the sandbox is still active).
    """

    STRICT = "strict"
    STANDARD = "standard"
    RELAXED = "relaxed"
    BYPASS = "bypass"

    @classmethod
    def from_str(cls, value: str) -> "RigorLevel":
        """Parse a case-insensitive string into a ``RigorLevel``."""
        try:
            return cls(value.lower())
        except ValueError:
            logger.warning(
                "Unknown rigor level %r — falling back to STANDARD", value,
            )
            return cls.STANDARD


# ── Default patterns ────────────────────────────────────────────────────
# Each entry is (regex, message, Severity).

DEFAULT_FORBIDDEN_PATTERNS: List[Tuple[str, str, Severity]] = [
    # Synthetic data generation
    (
        r"np\.random\.(rand|randn|random|uniform|normal|choice)\s*\(",
        "RIGOR VIOLATION: Random/synthetic data generation detected. "
        "Use real experimental data only.",
        Severity.WARNING,
    ),
    (
        r"random\.(random|uniform|gauss|choice)\s*\(",
        "RIGOR VIOLATION: Random data generation detected. "
        "Use real experimental data only.",
        Severity.WARNING,
    ),
    (
        r"fake|dummy|synthetic|simulated",
        "RIGOR VIOLATION: Code references fake/synthetic data. "
        "Use real experimental data only.",
        Severity.WARNING,
    ),
    # Result manipulation — CRITICAL, always block
    (
        r"if.*p.?value.*[<>].*0\.05.*:.*=",
        "RIGOR VIOLATION: Conditional result modification based on p-value detected.",
        Severity.CRITICAL,
    ),
    (
        r"result\s*=\s*(expected|hypothesis|target)",
        "RIGOR VIOLATION: Result forced to match expected/hypothesis value.",
        Severity.CRITICAL,
    ),
    (
        r"#.*hack|#.*fudge|#.*fake",
        "RIGOR VIOLATION: Code contains suspicious comments suggesting data manipulation.",
        Severity.WARNING,
    ),
    # Shell / subprocess escape — WARNING (the AST gate is the hard security boundary)
    (
        r"subprocess\.(run|Popen|call|check_output|check_call)\s*\(",
        "RIGOR WARNING: Shell subprocess execution detected — "
        "analysis code must run through the sandbox, not via shell.",
        Severity.WARNING,
    ),
    (
        r"os\.(system|popen|exec[lv]?[pe]?)\s*\(",
        "RIGOR WARNING: OS-level command execution detected — "
        "use the sandbox for analysis code.",
        Severity.WARNING,
    ),
    (
        r"powershell|cmd\.exe|/bin/(ba)?sh",
        "RIGOR WARNING: Direct shell invocation detected — "
        "all analysis must go through the sandbox.",
        Severity.WARNING,
    ),
]

DEFAULT_WARNING_PATTERNS: List[Tuple[str, str, Severity]] = [
    (
        r"np\.random\.seed",
        "Random seed set — ensure this is for reproducibility, not cherry-picking.",
        Severity.WARNING,
    ),
    (
        r"outlier.*remove|remove.*outlier",
        "Outlier removal detected — document criteria and report how many removed.",
        Severity.WARNING,
    ),
    (
        r"exclude|skip|ignore",
        "Data exclusion detected — document criteria and report what was excluded.",
        Severity.WARNING,
    ),
]

# Legacy 2-tuple aliases used by ``AgentConfig.forbidden_patterns`` and
# ``AgentConfig.warning_patterns`` — callers may pass either 2- or
# 3-tuples; ``_normalise_pattern`` upgrades 2-tuples on the fly.


def _normalise_pattern(
    entry: Tuple[str, ...], default_severity: Severity,
) -> Tuple[str, str, Severity]:
    """Accept ``(pattern, msg)`` or ``(pattern, msg, Severity)``."""
    if len(entry) == 3:
        return (entry[0], entry[1], entry[2])  # type: ignore[return-value]
    return (entry[0], entry[1], default_severity)


class CodeScanner:
    """Scan code for scientific-rigor violations.

    The scanner ships with a default set of forbidden/warning patterns
    that cover the most common scientific integrity issues.  Domain-specific
    agents can extend the lists via :meth:`add_forbidden` and
    :meth:`add_warning`.

    Behaviour is governed by ``rigor_level``:

    * ``STRICT``  — all matches become hard-block violations.
    * ``STANDARD`` (default) — CRITICAL patterns hard-block; WARNING
      patterns require user confirmation.
    * ``RELAXED`` — CRITICAL patterns require confirmation; WARNING
      patterns are informational.
    * ``BYPASS``  — scanner disabled (AST security gate still active).

    Example::

        scanner = CodeScanner(rigor_level=RigorLevel.STANDARD)
        scanner.add_forbidden(
            r"find_peaks\\s*\\(\\s*voltage",
            "Use detect_spikes tool instead of scipy find_peaks on voltage.",
        )
        result = scanner.check(user_code)
        if not result["passed"]:
            raise RuntimeError(result["violations"])
    """

    def __init__(self, rigor_level: RigorLevel = RigorLevel.STANDARD) -> None:
        self.rigor_level = rigor_level
        self._forbidden: List[Tuple[str, str, Severity]] = list(DEFAULT_FORBIDDEN_PATTERNS)
        self._warnings: List[Tuple[str, str, Severity]] = list(DEFAULT_WARNING_PATTERNS)

    # -- extension API --------------------------------------------------------

    def add_forbidden(
        self, pattern: str, message: str, severity: Severity = Severity.CRITICAL,
    ) -> None:
        """Add a regex pattern that *blocks* code execution."""
        self._forbidden.append((pattern, message, severity))

    def add_warning(
        self, pattern: str, message: str, severity: Severity = Severity.WARNING,
    ) -> None:
        """Add a regex pattern that produces a *warning* but allows execution."""
        self._warnings.append((pattern, message, severity))

    def add_forbidden_batch(self, patterns: List[Tuple[str, str]] | List[Tuple[str, str, Severity]]) -> None:
        """Add multiple forbidden patterns at once (2- or 3-tuples)."""
        self._forbidden.extend(
            _normalise_pattern(p, Severity.CRITICAL) for p in patterns  # type: ignore[arg-type]
        )

    def add_warning_batch(self, patterns: List[Tuple[str, str]] | List[Tuple[str, str, Severity]]) -> None:
        """Add multiple warning patterns at once (2- or 3-tuples)."""
        self._warnings.extend(
            _normalise_pattern(p, Severity.WARNING) for p in patterns  # type: ignore[arg-type]
        )

    # -- scanning -------------------------------------------------------------

    def check(self, code: str) -> Dict[str, Any]:
        """Scan *code* for rigor violations and warnings.

        Returns a dict with:

        * ``passed`` — ``True`` if no hard-block violations were found.
        * ``violations`` — messages that **block** execution outright.
        * ``needs_confirmation`` — messages that require user confirmation
          before the code may run.
        * ``warnings`` — informational messages (execution continues).

        The classification depends on the current ``rigor_level``.
        """
        if self.rigor_level == RigorLevel.BYPASS:
            return {
                "passed": True,
                "violations": [],
                "needs_confirmation": [],
                "warnings": [],
            }

        violations: List[str] = []
        needs_confirmation: List[str] = []
        warnings: List[str] = []

        all_patterns = list(self._forbidden) + list(self._warnings)

        for pattern, message, severity in all_patterns:
            if not re.search(pattern, code, re.IGNORECASE):
                continue
            self._classify(severity, message, violations, needs_confirmation, warnings)

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "needs_confirmation": needs_confirmation,
            "warnings": warnings,
        }

    # -- internal classification ----------------------------------------------

    def _classify(
        self,
        severity: Severity,
        message: str,
        violations: List[str],
        needs_confirmation: List[str],
        warnings: List[str],
    ) -> None:
        """Route *message* into the right bucket based on rigor level."""
        level = self.rigor_level

        if level == RigorLevel.STRICT:
            # Everything is a hard block in strict mode.
            violations.append(message)

        elif level == RigorLevel.STANDARD:
            if severity == Severity.CRITICAL:
                violations.append(message)
            else:
                needs_confirmation.append(message)

        elif level == RigorLevel.RELAXED:
            if severity == Severity.CRITICAL:
                needs_confirmation.append(message)
            else:
                warnings.append(message)

        # BYPASS is handled above (early-return).
