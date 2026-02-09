"""
Generic fitting tools — curve fitting utilities reusable across domains.

Only domain-agnostic fits live here.  Domain-specific fits (IV curves,
f-I curves, dose-response curves, etc.) belong in the domain agent's
own tools package.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import curve_fit


def fit_exponential(
    y: np.ndarray,
    x: np.ndarray,
    fit_type: str = "decay",
    p0: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Fit single exponential decay or growth.

    Args:
        y: Y values.
        x: X values.
        fit_type: ``"decay"`` or ``"growth"``.
        p0: Initial guess ``[amplitude, tau, offset]``.

    Returns:
        Dict with ``amplitude``, ``tau``, ``offset``, ``r_squared``,
        ``fitted_values``, and ``success``.
    """
    if fit_type == "decay":
        def exp_func(t, amp, tau, offset):
            return amp * np.exp(-t / tau) + offset
    else:
        def exp_func(t, amp, tau, offset):
            return amp * (1 - np.exp(-t / tau)) + offset

    x_norm = x - x[0]

    if p0 is None:
        amp_guess = y[0] - y[-1] if fit_type == "decay" else y[-1] - y[0]
        tau_guess = (x[-1] - x[0]) / 3
        offset_guess = y[-1] if fit_type == "decay" else y[0]
        p0 = [amp_guess, tau_guess, offset_guess]

    try:
        bounds = ([-np.inf, 1e-6, -np.inf], [np.inf, np.inf, np.inf])
        popt, pcov = curve_fit(exp_func, x_norm, y, p0=p0, bounds=bounds, maxfev=5000)
        amp, tau, offset = popt

        y_fit = exp_func(x_norm, *popt)
        residuals = y - y_fit
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "amplitude": float(amp),
            "tau": float(tau),
            "offset": float(offset),
            "r_squared": float(r_squared),
            "fitted_values": y_fit,
            "success": True,
        }
    except Exception as e:
        return {
            "amplitude": None,
            "tau": None,
            "offset": None,
            "r_squared": None,
            "fitted_values": None,
            "success": False,
            "error": str(e),
        }


def fit_double_exponential(
    y: np.ndarray,
    x: np.ndarray,
    p0: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Fit double exponential decay.

    ``y = A1 * exp(-x/tau1) + A2 * exp(-x/tau2) + offset``

    Args:
        y: Y values.
        x: X values.
        p0: Initial guess ``[A1, tau1, A2, tau2, offset]``.

    Returns:
        Dict with fit parameters and quality metrics.
    """
    def double_exp(t, a1, tau1, a2, tau2, offset):
        return a1 * np.exp(-t / tau1) + a2 * np.exp(-t / tau2) + offset

    x_norm = x - x[0]

    if p0 is None:
        amp_total = y[0] - y[-1]
        p0 = [
            amp_total * 0.7, (x[-1] - x[0]) / 5,
            amp_total * 0.3, (x[-1] - x[0]) / 2,
            y[-1],
        ]

    try:
        bounds = ([0, 1e-6, 0, 1e-6, -np.inf], [np.inf, np.inf, np.inf, np.inf, np.inf])
        popt, pcov = curve_fit(double_exp, x_norm, y, p0=p0, bounds=bounds, maxfev=10000)
        a1, tau1, a2, tau2, offset = popt

        # Ensure tau1 < tau2 (fast / slow)
        if tau1 > tau2:
            a1, a2 = a2, a1
            tau1, tau2 = tau2, tau1

        y_fit = double_exp(x_norm, *popt)
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "amplitude_fast": float(a1),
            "tau_fast": float(tau1),
            "amplitude_slow": float(a2),
            "tau_slow": float(tau2),
            "offset": float(offset),
            "r_squared": float(r_squared),
            "fitted_values": y_fit,
            "success": True,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
