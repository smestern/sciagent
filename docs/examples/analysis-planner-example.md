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

### 1. Research Question (Restated)

> Scan the opto_patch_data directory tree for all ABF files using the **"IC1"** protocol, then extract the **frequency–input (F-I) curve** (spike frequency vs. injected current) from each file.

### 2. Data Survey

| Property | Value |
|---|---|
| Total ABF files | 909 |
| **IC1 protocol files** | **151** (+ 1 with "2_ IC1_50hz") |
| Sweep count | 11–15 depending on cell (varies by max current step) |
| Sampling rate | 50,000 Hz (consistent) |
| Sweep length | 5.0 s |
| Y units | mV (membrane potential) |
| C units | pA (injected current) |

**Protocol structure** (consistent across all files):
1. **Holding** at 0 pA (0 – 0.278 s)
2. **Hyperpolarizing pre-step** –20 pA (0.278 – 0.578 s, ~300 ms) — for input resistance measurement
3. **Test current step** (0.578 – 1.278 s, **700 ms**) — varies per sweep: –10 to +120 pA in 10 pA increments
4. **Return to holding** (1.278 – 5.0 s)

**Variability noted**: Some files have only 11 or 13 sweeps (max step 80–100 pA instead of 120 pA). The epoch timings are consistent.

### 3. Pipeline Design

| # | Step | Action | Tool/Library | Expected Output | Checkpoint |
|---|---|---|---|---|---|
| 1 | **Find IC1 files** | `glob` + `pyabf.ABF(loadData=False)` to filter by `abf.protocol == "IC1"` | `pyabf`, `glob` | List of ~151 file paths | Count matches known total |
| 2 | **Load & parse** | For each file: load all sweeps with `pyabf`, extract time (`sweepX`), voltage (`sweepY`), command (`sweepC`) | `pyabf`, `numpy` | Arrays `(n_sweeps, n_samples)` | Shapes consistent; units = mV/pA |
| 3 | **Extract epoch timing** | From command waveform: detect transitions in `sweepC` to find step onset/offset | `numpy` | `step_start`, `step_end` in seconds | Values ≈ 0.578 s and 1.278 s |
| 4 | **Extract step current** | For each sweep: read the command level during the test epoch | `numpy` | Array of injected currents (pA) per sweep | Range from –20 to +120 pA, monotonic |
| 5 | **Spike detection** | During the step epoch: use `scipy.signal.find_peaks` with threshold-based detection (threshold crossing > 0 mV, `height=0`, `distance` ≥ 2 ms = 100 samples) | `scipy.signal` | Array of spike times per sweep | Visual inspection of traces with detected spikes |
| 6 | **Compute firing rate** | `n_spikes / step_duration` for each sweep | `numpy` | Spike frequency (Hz) per sweep | 0 Hz for subthreshold sweeps; plausible range 0–200 Hz |
| 7 | **Build F-I table** | Compile `(file, sweep, current_pA, n_spikes, freq_Hz)` into a DataFrame | `pandas` | One row per sweep per file | No NaN in required columns |
| 8 | **Save & plot** | Save CSV; plot per-cell F-I curves + population mean ± SEM | `matplotlib`, `pandas` | CSV file + PNG figure | Curves are monotonically non-decreasing |

### 4. Parameter Choices

| Parameter | Value | Justification |
|---|---|---|
| Spike detection threshold | 0 mV (`height=0`) | Standard for action potential detection in current clamp |
| Minimum inter-spike interval | 2 ms (`distance=100` samples at 50 kHz) | Prevents double-counting; absolute refractory period ≈ 1–2 ms |
| Step epoch | Detected from command waveform transitions | Robust to small protocol variations |
| Step duration | `step_end - step_start` (~0.7 s) | Directly measured from the command waveform |

### 5. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Some files may have different sweep counts/step ranges | Dynamically detect from command waveform per file; don't hardcode |
| Spike detection may fail on noisy/depolarization-blocked sweeps | Use `prominence` parameter as secondary filter; flag sweeps where max voltage is near 0 mV but no clear spikes detected |
| Cells may spike during pre-step or holding (spontaneously active) | Only count spikes during the step epoch |
| File read errors (Dropbox sync/corruption) | Try/except per file, skip and log errors |
| "2_ IC1_50hz" protocol may have different structure | Include as optional; verify epoch structure matches IC1 |

### 6. Success Criteria

- F-I curves are **monotonically non-decreasing** (higher current → equal or higher firing rate)
- Subthreshold sweeps (low current) show 0 Hz
- Peak firing rates are physiologically plausible (typically 5–200 Hz for most neuron types)
- All 151 IC1 files processed or explicitly logged as errors
- Output CSV contains one row per sweep per cell with: `file`, `sweep`, `current_pA`, `n_spikes`, `freq_Hz`

### 7. Incremental Validation Plan

1. **Validate on 1 file** → inspect traces, check spike detection visually, verify F-I curve shape
2. **Batch of 3 files** from different dates → check consistency
3. **Full dataset** → process all 151 files, save results

---

Shall I proceed with implementation? I'll start with step 1 (validate on a single file) per the incremental execution principle.

