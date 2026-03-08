# <!-- REPLACE: library_display_name — The display name of the primary domain library, e.g. "IPFX", "scanpy", "MNE-Python", "Biopython" --> API Reference

> **Source**: <!-- REPLACE: library_source_url — URL to the library's source repository. Example: "https://github.com/AllenInstitute/ipfx" -->
> **Docs**: <!-- REPLACE: library_docs_url — URL to the library's official documentation. Example: "https://ipfx.readthedocs.io/en/latest/" -->
> **Purpose**: This document provides the correct API surface for the
> primary domain library that your agent wraps or exposes. It is the
> authoritative reference for parameter names, types, defaults, and return
> values.

---

## Table of Contents

<!-- REPLACE: library_toc — A numbered list linking to each major section. Example:
1. [Core Module](#1-core-module)
   - [MainClass](#mainclass)
   - [HelperClass](#helperclass)
2. [Analysis Functions](#2-analysis-functions)
3. [Common Pitfalls](#3-common-pitfalls)
4. [Quick-Start Recipes](#4-quick-start-recipes)
-->

1. [Core Classes](#1-core-classes)
2. [Key Functions](#2-key-functions)
3. [Common Pitfalls](#3-common-pitfalls)
4. [Quick-Start Recipes](#4-quick-start-recipes)

---

## 1. Core Classes

<!-- REPLACE: library_core_classes — Document the main classes the agent will use. For each class, include: import statement, constructor signature with parameter descriptions, and key methods with their signatures and return types. Example:

### `MainAnalyzer`

Primary entry point for analysis.

```python
from my_library import MainAnalyzer
```

#### Constructor

```python
MainAnalyzer(
    threshold=0.5,      # float — detection threshold (unitless)
    window_size=100,     # int — analysis window in samples
    method="default",    # str — algorithm variant ("default", "fast", "precise")
)
```

> ⚠️ Note any common parameter confusion here (e.g. units, naming conflicts).

#### `.run(data, **kwargs) → ResultObject`

Run the analysis pipeline.

**Arguments**:
| Param | Type | Units | Description |
|-------|------|-------|-------------|
| `data` | `np.ndarray` | — | Input data array |
| `normalize` | `bool` | — | Pre-normalize input (default: True) |

**Returns**: `ResultObject` with attributes `.values`, `.metadata`, `.quality`.
-->

*Document your primary library's core classes here.*

---

## 2. Key Functions

<!-- REPLACE: library_key_functions — Document standalone functions the agent will call. For each function: signature, parameter table, return value description. Example:

### `detect_events(signal, threshold=0.5, min_duration=10)`

Detect events in a 1-D signal.

**Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `signal` | `np.ndarray` | required | 1-D input signal |
| `threshold` | `float` | 0.5 | Detection threshold |
| `min_duration` | `int` | 10 | Minimum event duration (samples) |

**Returns**: `List[Dict]` — one dict per detected event with keys
`start_index`, `end_index`, `amplitude`, `duration`.
-->

*Document your primary library's key functions here.*

---

## 3. Common Pitfalls

<!-- REPLACE: library_common_pitfalls — List gotchas, common mistakes, and parameter confusion that the agent should avoid. Example:

### Parameter `filter` vs `filter_frequency`
- `MainAnalyzer` uses `filter` (in kHz)
- `TrainAnalyzer` uses `filter_frequency` (also kHz, but for a different purpose)
- Do NOT confuse them — using the wrong parameter name silently uses the default

### Empty results
- `.run()` returns an **empty DataFrame** (not `None`) when no events are found
- Always check `len(result)` before accessing rows

### Unit mismatches
- Time arrays must be in **seconds**, not milliseconds
- Voltage must be in **mV**, current in **pA**
- The library will not warn you if units are wrong — results will just be incorrect
-->

*List common mistakes and gotchas specific to this library.*

---

## 4. Quick-Start Recipes

<!-- REPLACE: library_recipes — Copy-paste code snippets for the most common tasks. Each recipe should be self-contained with imports, data loading, analysis, and result access. Example:

### Recipe 1: Basic Event Detection

```python
import numpy as np
from my_library import MainAnalyzer

# Load data
data = np.load("recording.npy")
time = np.arange(len(data)) / sample_rate

# Detect events
analyzer = MainAnalyzer(threshold=0.5)
results = analyzer.run(data)

# Access results
print(f"Found {len(results)} events")
for i, event in results.iterrows():
    print(f"  Event {i}: amplitude={event['amplitude']:.1f}, "
          f"duration={event['duration']:.3f}s")
```

### Recipe 2: Batch Analysis

```python
from pathlib import Path
from my_library import MainAnalyzer, load_file

analyzer = MainAnalyzer()
results = {}

for path in Path("data/").glob("*.dat"):
    data = load_file(path)
    results[path.stem] = analyzer.run(data)
```
-->

*Provide copy-paste recipes for common analysis tasks.*

---

## Notes

- This document should be kept in sync with the library version your
  agent targets.
- When the library is updated, review parameter names, defaults, and
  return value schemas for breaking changes.
- If the library has multiple major classes or modules, consider splitting
  this into multiple reference files.
