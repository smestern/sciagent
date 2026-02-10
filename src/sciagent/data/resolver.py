"""
BaseDataResolver — Abstract base for flexible data input resolution.

Subclass and register domain-specific file formats via
:meth:`register_format`.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


# ── Working-directory resolution ────────────────────────────────────────

def resolve_working_dir(file_path: str, agent_name: str) -> Path:
    """Resolve a working directory adjacent to the analysed file.

    Strategy:
    1. Try ``<file_parent>/<agent_name>_output/``
    2. If the parent directory is not writable, fall back to a temp dir.

    Args:
        file_path: Path to the data file being analysed.
        agent_name: Short agent name used as directory prefix.

    Returns:
        An existing, writable directory ``Path``.
    """
    parent = Path(file_path).resolve().parent
    preferred = parent / f"{agent_name}_output"

    if os.access(str(parent), os.W_OK):
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            logger.info(
                "Working directory resolved near file: %s", preferred,
            )
            return preferred
        except OSError as exc:
            logger.warning(
                "Cannot create %s (%s), falling back to temp dir", preferred, exc,
            )

    fallback = Path(tempfile.mkdtemp(prefix=f"{agent_name}_"))
    logger.info(
        "Working directory fallback (parent not writable): %s", fallback,
    )
    return fallback


class BaseDataResolver:
    """Resolve various input types to standardised data arrays.

    Supports:
    - File paths (dispatched to registered format loaders)
    - NumPy arrays (pass-through with optional shape normalisation)
    - Dicts with named arrays
    - Lists of arrays or file paths

    Example::

        class MyResolver(BaseDataResolver):
            def __init__(self):
                super().__init__()
                self.register_format(".csv", self._load_csv)

            def _load_csv(self, path):
                import pandas as pd
                df = pd.read_csv(path)
                return df.values, None
    """

    def __init__(
        self,
        use_cache: bool = True,
        max_cache_size: int = 50,
        default_sample_rate: float = 1.0,
    ):
        self.use_cache = use_cache
        self.max_cache_size = max_cache_size
        self.default_sample_rate = default_sample_rate

        self._format_loaders: Dict[str, Callable] = {}
        self._cache: Dict[str, Any] = {}

    # -- format registration --------------------------------------------------

    def register_format(
        self, extension: str, loader_fn: Callable
    ) -> None:
        """Register a loader for a file extension.

        Args:
            extension: File extension including dot (e.g. ``".csv"``).
            loader_fn: Callable ``(path: str) -> tuple`` that returns
                       loaded data.  The exact tuple shape is determined
                       by the subclass.
        """
        self._format_loaders[extension.lower()] = loader_fn

    # -- resolution -----------------------------------------------------------

    def resolve(
        self,
        data: Union[str, Path, np.ndarray, List, Dict[str, Any]],
        **kwargs,
    ) -> Any:
        """Resolve *data* to a usable form.

        Args:
            data: Input in one of the supported formats.

        Returns:
            The resolved data (shape depends on subclass).
        """
        if isinstance(data, (str, Path)):
            return self._load_file(str(data), **kwargs)

        if isinstance(data, np.ndarray):
            return self._resolve_array(data)

        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError("Empty list provided")
            if isinstance(data[0], str):
                logger.info("List of %d files provided, loading first", len(data))
                return self._load_file(data[0], **kwargs)
            if isinstance(data[0], np.ndarray):
                return self._resolve_array_list(data)

        if isinstance(data, dict):
            return self._resolve_dict(data)

        raise TypeError(f"Unsupported data type: {type(data)}")

    # -- file loading ---------------------------------------------------------

    def _load_file(self, file_path: str, **kwargs) -> Any:
        """Load a file, using cache if available."""
        # Cache check
        if self.use_cache and file_path in self._cache:
            logger.debug("Cache hit: %s", file_path)
            return self._cache[file_path]

        ext = Path(file_path).suffix.lower()
        loader = self._format_loaders.get(ext)
        if loader is None:
            supported = ", ".join(self._format_loaders.keys()) or "(none)"
            raise ValueError(
                f"No loader registered for '{ext}'. "
                f"Supported formats: {supported}"
            )

        logger.info("Loading file: %s", file_path)
        result = loader(file_path, **kwargs)

        if self.use_cache:
            self._add_to_cache(file_path, result)

        return result

    # -- array resolution (override for domain-specific shapes) ---------------

    def _resolve_array(self, arr: np.ndarray) -> Any:
        """Resolve a bare NumPy array.  Override for domain shapes."""
        return arr

    def _resolve_array_list(self, arrays: List[np.ndarray]) -> Any:
        """Resolve a list of NumPy arrays.  Override for domain shapes."""
        return arrays

    def _resolve_dict(self, data: Dict[str, Any]) -> Any:
        """Resolve a dict of named arrays.  Override for domain shapes."""
        return data

    # -- cache management -----------------------------------------------------

    def _add_to_cache(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_cache_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug("Cache eviction: %s", oldest_key)
        self._cache[key] = value

    def clear_cache(self) -> None:
        """Clear the file cache."""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_cache_size,
            "files": list(self._cache.keys()),
        }
