"""
BoundsChecker — sanity-check measured values against expected ranges.

Domain agents provide a dict of ``parameter_name → (lower, upper)``
tuples.  The checker flags values outside those ranges.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class BoundsChecker:
    """Check measured values against domain-specific expected ranges.

    Example::

        checker = BoundsChecker({
            "temperature_C": (0, 100),
            "pressure_atm": (0.5, 2.0),
        })
        result = checker.check(37.0, "temperature_C")
        assert result["valid"]
    """

    def __init__(self, bounds: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self._bounds: Dict[str, Tuple[float, float]] = dict(bounds or {})

    def add(self, parameter: str, lower: float, upper: float) -> None:
        """Register (or replace) bounds for a parameter."""
        self._bounds[parameter] = (lower, upper)

    def update(self, bounds: Dict[str, Tuple[float, float]]) -> None:
        """Merge multiple bounds at once."""
        self._bounds.update(bounds)

    def check(
        self,
        value: float,
        parameter: str,
        custom_bounds: Optional[Tuple[float, float]] = None,
    ) -> Dict[str, Any]:
        """Check a single value.

        Args:
            value: The measured value.
            parameter: Key in the bounds dict.
            custom_bounds: One-off ``(lower, upper)`` override.

        Returns:
            Dict with ``valid``, ``value``, ``bounds``, and optional ``warning``.
        """
        bounds: Optional[Tuple[float, float]] = custom_bounds
        if bounds is None:
            bounds = self._bounds.get(parameter)

        if bounds is None:
            return {
                "valid": None,
                "value": value,
                "bounds": None,
                "note": f"No bounds defined for '{parameter}'",
            }

        is_valid = bounds[0] <= value <= bounds[1]
        result: Dict[str, Any] = {
            "valid": is_valid,
            "value": value,
            "bounds": bounds,
        }

        if not is_valid:
            result["warning"] = (
                f"Value {value} for '{parameter}' is outside expected range "
                f"[{bounds[0]}, {bounds[1]}]. This may indicate an instrument issue, "
                f"analysis error, or genuinely unusual measurement. Investigate before proceeding."
            )

        return result

    def check_many(self, measurements: Dict[str, float]) -> List[Dict[str, Any]]:
        """Check multiple parameter→value pairs at once."""
        return [self.check(v, k) for k, v in measurements.items()]

    @property
    def bounds(self) -> Dict[str, Tuple[float, float]]:
        """Read-only access to registered bounds."""
        return dict(self._bounds)
