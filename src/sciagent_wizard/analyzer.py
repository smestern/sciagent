"""
Example data analyzer — infer domain metadata from uploaded files.

Given one or more example data files the researcher provides, this module
determines:
- File extensions → ``accepted_file_types``
- Column names, dtypes, value ranges → ``bounds``
- Statistical signatures → guardrail hints, workflow suggestions
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from sciagent_wizard.models import DataFileInfo

logger = logging.getLogger(__name__)

# Extensions we can introspect natively
_TABULAR_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".feather"}
_ARRAY_EXTS = {".npy", ".npz"}
_TEXT_EXTS = {".txt", ".json", ".jsonl"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
_BIO_EXTS = {".abf", ".nwb", ".fasta", ".fastq", ".bam", ".sam", ".vcf", ".bed", ".gff"}
_ALL_KNOWN = _TABULAR_EXTS | _ARRAY_EXTS | _TEXT_EXTS | _IMAGE_EXTS | _BIO_EXTS


def analyze_example_files(file_paths: List[str]) -> List[DataFileInfo]:
    """Analyze a list of example data files.

    Args:
        file_paths: Absolute paths to example data files.

    Returns:
        List of ``DataFileInfo`` with inferred metadata.
    """
    results: List[DataFileInfo] = []
    for fp in file_paths:
        try:
            info = _analyze_single(fp)
            results.append(info)
        except Exception as exc:
            logger.warning("Failed to analyse %s: %s", fp, exc)
            results.append(
                DataFileInfo(
                    path=fp,
                    extension=Path(fp).suffix.lower(),
                    inferred_domain_hints=[f"Could not auto-analyze: {exc}"],
                )
            )
    return results


def infer_accepted_types(infos: List[DataFileInfo]) -> List[str]:
    """Derive a unique sorted list of accepted file extensions."""
    exts = set()
    for info in infos:
        if info.extension:
            exts.add(info.extension)
    return sorted(exts)


def infer_bounds(infos: List[DataFileInfo]) -> Dict[str, Tuple[float, float]]:
    """Derive ``BoundsChecker`` ranges from analyzed data columns.

    For each numeric column, the bound is set to::
        (min_value - 0.2 * range, max_value + 0.2 * range)

    giving a 20 % margin around observed values.
    """
    bounds: Dict[str, Tuple[float, float]] = {}
    for info in infos:
        for col, (lo, hi) in info.value_ranges.items():
            margin = 0.2 * max(abs(hi - lo), 1e-12)
            bounds[col] = (round(lo - margin, 6), round(hi + margin, 6))
    return bounds


def collect_domain_hints(infos: List[DataFileInfo]) -> List[str]:
    """Aggregate domain hints from all files."""
    hints: list[str] = []
    for info in infos:
        hints.extend(info.inferred_domain_hints)
    return list(dict.fromkeys(hints))  # deduplicate preserving order


# ── Internal per-file analysis ──────────────────────────────────────────


def _analyze_single(file_path: str) -> DataFileInfo:
    """Analyze a single data file."""
    p = Path(file_path)
    ext = p.suffix.lower()
    info = DataFileInfo(path=file_path, extension=ext)

    if ext in _TABULAR_EXTS:
        _analyze_tabular(p, info)
    elif ext in _ARRAY_EXTS:
        _analyze_numpy(p, info)
    elif ext in _TEXT_EXTS:
        _analyze_text(p, info)
    elif ext in _IMAGE_EXTS:
        info.inferred_domain_hints.append("image_data")
    elif ext in _BIO_EXTS:
        info.inferred_domain_hints.append(f"domain_file_format:{ext}")
    else:
        info.inferred_domain_hints.append(f"unknown_extension:{ext}")

    return info


def _analyze_tabular(path: Path, info: DataFileInfo) -> None:
    """Analyze a tabular file (CSV, TSV, Excel, Parquet)."""
    try:
        import pandas as pd
    except ImportError:
        info.inferred_domain_hints.append("pandas_not_installed")
        return

    try:
        if path.suffix.lower() in {".csv", ".tsv"}:
            sep = "\t" if path.suffix.lower() == ".tsv" else ","
            df = pd.read_csv(path, sep=sep, nrows=5000)
        elif path.suffix.lower() in {".xlsx", ".xls"}:
            df = pd.read_excel(path, nrows=5000)
        elif path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path)
            if len(df) > 5000:
                df = df.head(5000)
        elif path.suffix.lower() == ".feather":
            df = pd.read_feather(path)
            if len(df) > 5000:
                df = df.head(5000)
        else:
            return
    except Exception as exc:
        info.inferred_domain_hints.append(f"read_error:{exc}")
        return

    info.columns = list(df.columns.astype(str))
    info.dtypes = {str(c): str(df[c].dtype) for c in df.columns}
    info.row_count = len(df)

    # Value ranges for numeric columns
    numeric = df.select_dtypes(include=[np.number])
    for col in numeric.columns:
        series = numeric[col].dropna()
        if len(series) > 0:
            info.value_ranges[str(col)] = (float(series.min()), float(series.max()))

    # Domain hints from column names
    col_lower = [c.lower() for c in info.columns]
    _hint_from_columns(col_lower, info)


def _analyze_numpy(path: Path, info: DataFileInfo) -> None:
    """Analyze a .npy or .npz file."""
    try:
        if path.suffix == ".npy":
            arr = np.load(str(path), allow_pickle=False)
            info.row_count = arr.shape[0] if arr.ndim > 0 else 1
            info.columns = [f"dim_{i}" for i in range(arr.ndim)]
            info.dtypes = {"array": str(arr.dtype)}
            if arr.ndim <= 2 and np.issubdtype(arr.dtype, np.number):
                info.value_ranges["array"] = (float(np.nanmin(arr)), float(np.nanmax(arr)))
        elif path.suffix == ".npz":
            data = np.load(str(path), allow_pickle=False)
            info.columns = list(data.files)
            for key in data.files:
                arr = data[key]
                info.dtypes[key] = str(arr.dtype)
                if np.issubdtype(arr.dtype, np.number) and arr.size > 0:
                    info.value_ranges[key] = (float(np.nanmin(arr)), float(np.nanmax(arr)))
            info.row_count = sum(data[k].shape[0] for k in data.files if data[k].ndim > 0)
    except Exception as exc:
        info.inferred_domain_hints.append(f"numpy_read_error:{exc}")


def _analyze_text(path: Path, info: DataFileInfo) -> None:
    """Analyze JSON/JSONL/text files (just basic structure)."""
    import json

    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:50_000]
    except Exception:
        return

    if path.suffix == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, list):
                info.row_count = len(data)
                if data and isinstance(data[0], dict):
                    info.columns = list(data[0].keys())
            elif isinstance(data, dict):
                info.columns = list(data.keys())
                info.row_count = 1
        except json.JSONDecodeError:
            pass
    elif path.suffix == ".jsonl":
        lines = text.strip().split("\n")
        info.row_count = len(lines)
        if lines:
            try:
                first = json.loads(lines[0])
                if isinstance(first, dict):
                    info.columns = list(first.keys())
            except json.JSONDecodeError:
                pass

    info.inferred_domain_hints.append("text_or_structured_data")


def _hint_from_columns(col_lower: List[str], info: DataFileInfo) -> None:
    """Infer domain hints from column names."""
    hints = info.inferred_domain_hints

    # Time series indicators
    time_cols = {"time", "t", "timestamp", "date", "datetime", "seconds", "ms", "minutes"}
    if time_cols & set(col_lower):
        hints.append("time_series_data")

    # Electrophysiology
    ephys_cols = {"voltage", "current", "mv", "pa", "na", "sweep", "trace", "membrane_potential"}
    if ephys_cols & set(col_lower):
        hints.append("electrophysiology_data")

    # Genomics
    genomics_cols = {"gene", "chromosome", "chr", "position", "snp", "allele", "sequence"}
    if genomics_cols & set(col_lower):
        hints.append("genomics_data")

    # Imaging
    imaging_cols = {"pixel", "intensity", "roi", "fluorescence", "channel", "frame"}
    if imaging_cols & set(col_lower):
        hints.append("imaging_data")

    # Chemistry
    chem_cols = {"smiles", "inchi", "molecular_weight", "mol_weight", "compound", "concentration"}
    if chem_cols & set(col_lower):
        hints.append("chemistry_data")

    # General statistics
    stats_cols = {"mean", "std", "sd", "sem", "p_value", "pvalue", "ci_lower", "ci_upper"}
    if stats_cols & set(col_lower):
        hints.append("statistical_summary_data")

    # Spectral data
    spectral_cols = {"wavelength", "frequency", "absorbance", "transmittance", "spectrum"}
    if spectral_cols & set(col_lower):
        hints.append("spectral_data")
