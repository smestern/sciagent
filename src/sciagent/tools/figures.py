"""
figures — Matplotlib figure capture and saving.

Extracts open matplotlib figures, encodes them as base64 PNG,
saves them to the output directory, and optionally pushes them
to a web UI queue.
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def capture_figures(
    output_dir: Optional[Path] = None,
    figure_push_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    """Capture all open matplotlib figures.

    Encodes each figure as base64 PNG, saves to *output_dir*
    if provided, and pushes to *figure_push_fn* for web UI display.

    Args:
        output_dir: Directory to save PNG files.
        figure_push_fn: Callback ``(fig_data) -> None`` for web UI queue.

    Returns:
        List of figure data dicts with ``figure_number``,
        ``image_base64``, and ``format`` keys.
    """
    figures_data: List[Dict[str, Any]] = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        open_figs = plt.get_fignums()
        if not open_figs:
            return figures_data

        for fig_num in open_figs:
            fig = plt.figure(fig_num)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            img_bytes = buf.read()
            fig_data = {
                "figure_number": fig_num,
                "image_base64": base64.b64encode(img_bytes).decode("utf-8"),
                "format": "png",
            }
            figures_data.append(fig_data)
            buf.close()

            # Save to disk
            _save_figure(fig_num, img_bytes, output_dir)

            # Push to web UI queue
            if figure_push_fn is not None:
                try:
                    figure_push_fn(fig_data)
                except Exception as q_err:
                    logger.debug("Failed to push figure to queue: %s", q_err)

        plt.close("all")

    except ImportError:
        pass
    except Exception as fig_err:
        logger.warning("Failed to capture matplotlib figures: %s", fig_err)

    return figures_data


def _save_figure(
    fig_num: int,
    img_bytes: bytes,
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Save a figure's PNG bytes to the output directory.

    The file is named ``figure_<num>_<timestamp>.png`` and is only
    written if it doesn't already exist (avoids duplicates).

    Returns:
        Path to the saved file, or ``None`` if not saved.
    """
    if output_dir is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fig_path = output_dir / f"figure_{fig_num}_{ts}.png"
    if not fig_path.exists():
        fig_path.write_bytes(img_bytes)
        logger.debug("Saved figure to %s", fig_path)
        return fig_path
    return None
