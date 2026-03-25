# Example: Data QC

> **Skill:** `/data-qc`
> **Domain:** <!-- Your domain here -->
> **Dataset:** <!-- Brief description, e.g. "CSV with 500 rows, 12 columns of behavioral measurements" -->

---

## Task

<!-- 1-2 sentences: what data did you ask the agent to check? Example: -->
<!-- "Run quality control on my experimental dataset before I start the analysis." -->

---

## Transcript

<!-- Paste the real conversation here. Annotate key moments with callout boxes like: -->

<!--
> **What's happening:** The QC skill checks for missing values, outliers,
> distributional anomalies, and unit consistency — not just basic null checks.

> **What's happening:** It flags that column "resistance_MOhm" has 3 values
> below 10 MΩ, which is physiologically implausible for healthy neurons.
> This is a domain-aware check, not just a statistical outlier test.

> **Why this matters:** A generic LLM would check for nulls and maybe z-score
> outliers. The data QC skill combines statistical checks with domain knowledge
> to catch values that are technically valid numbers but scientifically wrong.
-->

---

## QC Report

<!-- Paste or summarize the QC report. Example structure: -->

<!--
| # | Severity | Check | Finding |
|---|----------|-------|---------|
| 1 | CRITICAL | Missing data | Column `condition` has 12 NaN values (2.4%) |
| 2 | CRITICAL | Implausible values | 3 resistance values < 10 MΩ (seal integrity?) |
| 3 | WARNING | Distribution | `firing_rate` is heavily right-skewed (skew=3.2) |
| 4 | WARNING | Duplicates | 2 exact duplicate rows (indices 142, 143) |
| 5 | INFO | Units | All columns have consistent units within expected ranges |
-->

---

## Key Takeaway

<!-- What did SciAgent catch that a generic LLM wouldn't?
     e.g., "Caught that 3 recordings had implausibly low seal resistance — these
     would have passed a simple outlier test but indicate compromised recordings
     that should be excluded." -->
