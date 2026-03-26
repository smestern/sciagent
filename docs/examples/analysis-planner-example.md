# Example: Analysis Planner
>[!NOTE]
> **Skill:** `/analysis-planner`  
> **Domain:** Intracellular Electrophysiology  
> **Dataset:** 909 unsorted recordings from patch-clamp electrophysiology experiments
>
>---
>
>## Task
> In this task, the agent is tasked with designing an multipart analysis. The end-user is using a lot of domain specific lingo. First, it has to use domain knowledge to understand that `ABF` files are intracellular patch clamp electrophysiology. The user is asking for a 'frequency-input' curve, which essentially charecterizes how a neuron ['spikes'](https://en.wikipedia.org/wiki/Action_potential) in response to different stimulus magnitudes. To measure this, the plan should look something like:   
> (1) Load the file and detect spikes   
> (2) Read the applied stimulus from the file   
> (3) Compute the frequency by dividing the number of 'spikes' by the length of the applied stimulus  
> (4) Plot the stimulus magnitude (X) vs spike frequency (Y)
>
>---
>
>## Key Takeaway
>
> The planner translated a terse, jargon-heavy request ("find all IC1 files and extract the frequency-input curve") into a 7-step pipeline with concrete, physiologically-grounded parameters — a 0 mV spike threshold, a 2 ms refractory distance, and a plausible rheobase range of 20–400 pA — without the user specifying any of them. It also scanned the existing codebase and discovered `loadABF.py` and `pyAPisolation` already present, incorporating them as preferred tools with `scipy.signal.find_peaks` as a fallback. Crucially, the plan follows a **validate-on-one-then-scale** progression (single file → small batch → full dataset) with explicit checkpoints at each stage, and it anticipates domain-specific risks a generic LLM would miss: protocol name case/spacing variants, epoch-table-derived injection windows instead of assumed step sizes, and **depolarization block** at high currents, which it flags as real biology to report honestly rather than smooth away. The result is a plan that a domain scientist can audit and approve before a single line of code is written.
>
>---

# *Example: Transcript*

<div style="text-align: right">  <b>User:</b>

`/analysis-planner` In this folder and subfolders are several ABF files consisting of patch clamp recordings from neurons. I want you to write a script that finds all files with the protocol "IC1" and extracts the frequency-input curve.</div>

**Model:**  

## Analysis Plan: F-I Curve Extraction from IC1 Protocol ABF Files

### 1. Restatement of the Research Question

Extract frequency-input (F-I) curves from all patch-clamp ABF files whose pClamp protocol is named **"IC1"**. An IC1 protocol is a standard current-clamp step protocol: each sweep injects a different current amplitude (increasing steps), and the membrane voltage response is recorded. The F-I curve plots **firing frequency** (spikes/s) vs. **injected current** (pA) for each cell.

---

### 2. Data Survey Summary

| Property | Value |
|---|---|
| Total ABF files | ~909 across opto_patch_data subdirectories |
| File discovery pattern | `glob.glob("./opto_patch_data/**/*.abf", recursive=True)` |
| Existing loader | loadABF.py — returns `(time, voltage, command)` arrays via pyABF |
| Spike detection | `pyAPisolation.featureExtractor.analyze_spike_times` already used in analyze_justice_IC.py |
| Protocol accessor | `pyabf.ABF(path).protocol` gives the protocol name string |
| Units | Y-channel: mV (voltage), C-channel: pA (command current) |

**Unknown (will be resolved in Step 1):** The exact protocol string — could be `"IC1"`, `"IC 1"`, `"ic1"`, etc. The first step will inventory all unique protocol names to confirm the exact match.

---

### 3. Pipeline Design (Numbered Checklist)

#### Step 1 — Discover & Inventory Protocols
- **Action**: Scan all ABF files, read `abf.protocol` from each, collect unique protocol names
- **Tool/library**: `pyabf`, `glob`
- **Expected output**: A printed list of unique protocol names with file counts
- **Checkpoint**: Confirm "IC1" (or variant) appears; note total file count for that protocol

#### Step 2 — Load & Validate a Single IC1 File
- **Action**: Pick the first IC1 file. Load with `pyabf.ABF()`. Inspect:
  - Number of sweeps
  - Sweep duration, sample rate
  - Command waveform shape (should show current steps)
  - Y-channel units (`sweepUnitsY` should be "mV")
  - C-channel units (`sweepUnitsC` should be "pA")
  - Determine current injection epoch (start/end) from the command waveform or epoch table
- **Tool/library**: `pyabf`
- **Expected output**: A summary printout + a quick plot of one sweep (voltage + command overlay)
- **Checkpoint**: Current steps increase across sweeps; units are correct; injection window is identifiable

#### Step 3 — Spike Detection on One File
- **Action**: For each sweep, detect action potentials in the current injection window. Count spikes. Compute frequency = count / injection_duration.
- **Tool/library**: `scipy.signal.find_peaks` (simple, no extra dependency) or `pyAPisolation.featureExtractor.analyze_spike_times` (already in codebase)
- **Parameters**:
  - **Spike threshold**: Use a voltage threshold (e.g., 0 mV or dynamically set based on sweep baseline + N*SD). `find_peaks(height=0, distance=int(0.002*fs))` is a reasonable default for neurons (refractory ~2 ms).
  - **Injection window**: Derived from command waveform epoch start/end
- **Expected output**: Per-sweep: `(current_pA, spike_count, frequency_Hz)`
- **Checkpoint**: Subthreshold sweeps show 0 spikes; frequency increases monotonically with current (mostly); no spurious spikes outside injection window

#### Step 4 — Build F-I Curve for One Cell
- **Action**: Plot frequency (Hz) vs. injected current (pA) for the single validated file
- **Tool/library**: `matplotlib`
- **Expected output**: A clean F-I curve plot
- **Checkpoint**: Curve should be flat at 0 Hz for subthreshold currents, then rise. Rheobase should be a plausible value (typically 20–400 pA depending on cell type)

#### Step 5 — Small Batch Test (2–3 additional IC1 files)
- **Action**: Process 2–3 more IC1 files through the same pipeline. Compare results across cells.
- **Checkpoint**: Each F-I curve is plausible; no crashes or edge cases

#### Step 6 — Scale to All IC1 Files
- **Action**: Loop over all IC1 files. For each:
  1. Load ABF
  2. Extract current steps from command waveform
  3. Detect spikes per sweep
  4. Compute F-I curve
  5. Store results in a DataFrame
- **Expected output**: A CSV / DataFrame with columns: `file_path, cell_id, current_pA, spike_count, frequency_Hz`
- **Checkpoint**: All files processed without errors; no NaN/Inf values; distributions look reasonable

#### Step 7 — Aggregate Visualization & Export
- **Action**:
  - Plot individual F-I curves (one line per cell)
  - Plot mean ± SEM F-I curve across cells
  - Save results CSV and figure(s)
- **Tool/library**: `matplotlib`, `pandas`
- **Expected output**: Summary F-I plot + CSV file
- **Checkpoint**: Mean curve is smooth; error bars are reasonable; N is reported

---

### 4. Key Parameters

| Parameter | Default | Justification |
|---|---|---|
| Protocol filter | `"IC1"` (case-insensitive) | User-specified; will confirm in Step 1 |
| Spike height threshold | 0 mV | Standard for intracellular AP detection |
| Min spike distance | 2 ms (`distance = int(0.002 * fs)`) | Absolute refractory period |
| Injection window | Derived from `abf.sweepEpochs` | Epoch table gives exact start/end of step |

### 5. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Protocol name mismatch (e.g., "IC 1", "ic_1") | Step 1 inventories all protocol names; use case-insensitive substring match |
| Variable sweep counts / step sizes across files | Extract current per-sweep from command waveform rather than assuming a fixed step increment |
| Corrupted or truncated ABF files | Wrap loading in try/except; log and skip failures |
| Spike detection misses or false positives | Validate on single file first (Step 3); plot raw trace with detected peaks overlaid |
| pyAPisolation not installed | Fall back to `scipy.signal.find_peaks` (no extra install needed) |
| Sweeps with depolarization block (high current, reduced firing) | This is real biology — report it honestly, don't smooth it away |

### 6. Success Criteria

- All IC1-protocol ABF files identified and processed
- Per-cell F-I curves are sigmoidal / monotonically-increasing (until possible depol block)
- Rheobase and max firing rate are within physiologically plausible ranges
- Results are reproducible (deterministic code, no random components)
- Output CSV has no missing values for successfully processed files

---

### Recommended First Step

**Start with Step 1 (protocol inventory)** to confirm the exact "IC1" string and the number of files. This is quick and will validate that the pipeline target is correct before writing any analysis code.

To proceed, hand off to **sci-coder** with this plan. Would you like me to route to the coder agent now, or do you want to adjust any parameters first (e.g., spike detection method, threshold, specific output format)?

