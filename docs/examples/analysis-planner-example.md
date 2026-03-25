# Example: Analysis Planner

> **Skill:** `/analysis-planner`
> **Domain:** <!-- Your domain here, e.g. "Intracellular Electrophysiology" -->
> **Dataset:** <!-- Brief description, e.g. "48 ABF recordings across 3 conditions" -->

---

## Task

<!-- 1-2 sentences: what did you ask the agent to do? Example: -->
<!-- "Plan an analysis of firing rate changes across treatment conditions from whole-cell current-clamp recordings." -->

---

## Transcript

<!-- Paste the real conversation here. Annotate key moments with callout boxes like: -->

<!--
> **What's happening:** The planner identifies that data QC must run before any
> analysis — it won't skip straight to statistics even though you only asked
> about firing rates.

> **Why this matters:** A generic LLM would jump to code immediately. The planner
> enforces a structured pipeline: load → validate → analyze → review → report.
-->

---

## Generated Plan

<!-- Paste the step-by-step plan the agent produced. Example structure: -->

<!--
### Step 1: Data Loading & Inventory
- Load all .abf files from input directory
- Verify sweep count, sampling rate, protocol timing
- **Success criteria:** All files load without error; metadata consistent

### Step 2: Quality Control
- Check for seal resistance anomalies
- Flag recordings with unstable baseline
- **Risk:** Files with broken seal → exclude from analysis

### Step 3: Feature Extraction
...
-->

---

## Key Takeaway

<!-- What did SciAgent do here that a vanilla LLM wouldn't?
     e.g., "Identified that the stimulus protocol varies across files and added a
     normalization step before pooling — something a generic LLM would miss." -->
