"""
Data-integrity validation utilities.

Provides :func:`validate_data_integrity` and the ``SANITY_CHECK_HEADER``
code block that is auto-injected into sandbox executions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def validate_data_integrity(data: Any, name: str = "data") -> Dict[str, Any]:
    """Validate that input data is suitable for analysis.

    Checks for NaN/Inf, constant values, suspicious smoothness, all-zeros.

    Args:
        data: NumPy array or array-like.
        name: Label for error messages.

    Returns:
        Dict with ``valid``, ``issues``, ``warnings``, and ``stats``.
    """
    import numpy as np

    arr = np.asarray(data)
    issues: list[str] = []
    warnings: list[str] = []

    # NaN
    nan_count = int(np.sum(np.isnan(arr)))
    nan_pct = 100 * nan_count / arr.size if arr.size > 0 else 0
    if nan_count > 0:
        if nan_pct > 50:
            issues.append(f"{name}: {nan_pct:.1f}% NaN values — data may be corrupted")
        else:
            warnings.append(f"{name}: {nan_pct:.1f}% NaN values detected")

    # Inf
    inf_count = int(np.sum(np.isinf(arr)))
    if inf_count > 0:
        issues.append(f"{name}: {inf_count} Inf values detected — check instrument saturation")

    # Zero variance
    clean = arr[np.isfinite(arr)]
    if len(clean) > 0 and np.std(clean) == 0:
        issues.append(f"{name}: Zero variance — possible recording failure or disconnection")

    # All zeros
    if np.all(arr == 0):
        issues.append(f"{name}: All zeros — check instrument connection")

    # Suspicious smoothness
    if len(clean) > 1000:
        noise_ratio = np.std(np.diff(clean)) / (np.std(clean) + 1e-10)
        if noise_ratio < 0.0001:
            warnings.append(f"{name}: Suspiciously smooth — real data typically has noise")

    # Stats
    stats: Dict[str, Any] = {}
    if len(clean) > 0:
        stats = {
            "min": float(np.min(clean)),
            "max": float(np.max(clean)),
            "mean": float(np.mean(clean)),
            "std": float(np.std(clean)),
            "n_valid": int(len(clean)),
            "n_total": int(arr.size),
        }

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
        "name": name,
    }


# Code block auto-injected into sandbox executions
SANITY_CHECK_HEADER = '''\
# === AUTO-INJECTED SANITY CHECKS (Scientific Rigor) ===
import numpy as np

def _validate_input(arr, name="data"):
    """Validate input array before analysis. Raises on critical issues."""
    if arr is None:
        raise ValueError(f"RIGOR: {name} is None — cannot analyze missing data")
    arr = np.asarray(arr)
    if arr.size == 0:
        raise ValueError(f"RIGOR: {name} is empty — no data to analyze")
    nan_pct = 100 * np.sum(np.isnan(arr)) / arr.size
    if nan_pct > 50:
        raise ValueError(f"RIGOR: {name} is {nan_pct:.0f}% NaN — data is corrupted")
    elif nan_pct > 0:
        print(f"WARNING: {name} contains {nan_pct:.1f}% NaN values")
    if np.all(arr == 0):
        raise ValueError(f"RIGOR: {name} is all zeros — check recording")
    if np.std(arr[np.isfinite(arr)]) == 0:
        raise ValueError(f"RIGOR: {name} has zero variance — recording failure?")
    return arr

def _check_range(value, name, lo, hi):
    """Warn if value is outside expected range."""
    if not (lo <= value <= hi):
        print(f"WARNING: {name}={value:.4g} outside expected range [{lo}, {hi}]")
    return value

# === END SANITY CHECKS ===
'''
