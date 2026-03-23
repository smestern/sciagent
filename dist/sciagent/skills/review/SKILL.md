## Code Quality Review

---
name: code-reviewer
description: Reviews scientific analysis scripts for correctness, reproducibility, error handling, code quality, performance, and scientific best practices — provides severity-rated actionable feedback without modifying code.
argument-hint: Provide a script or code to review for correctness and best practices.
---

# Scientific Code Review

Use this skill when reviewing analysis scripts for correctness,
reproducibility, and adherence to scientific best practices.

## Review Checklist

### 1. Correctness

- Do computations match the described methodology?
- Are array operations broadcasting correctly?
- Are edge cases handled (empty arrays, single samples, NaN propagation)?
- Are indexing and slicing operations correct (off-by-one errors)?
- Are statistical tests used with correct assumptions?

### 2. Reproducibility

- Are random seeds set for all stochastic operations?
- Are library versions pinned or documented?
- Can the script run end-to-end from raw data to final output?
- Are hardcoded paths replaced with arguments or config?
- Is the output deterministic given the same input?

### 3. Error Handling

- Are file I/O operations wrapped in try/except?
- Are user inputs validated before use?
- Are informative error messages provided?
- Does the script fail gracefully on bad data?

### 4. Code Quality

- Are functions small, focused, and well-named?
- Are magic numbers replaced with named constants?
- Is there adequate documentation (docstrings, inline comments)?
- Are imports organized (stdlib → third-party → local)?
- Is dead code removed?

### 5. Performance

- Are there unnecessary loops that could be vectorized?
- Is data loaded efficiently (chunked reading for large files)?
- Are intermediate results cached when reused?

### 6. Scientific Best Practices

- Is data integrity maintained (no accidental mutation of input data)?
- Are units tracked and documented?
- Are analysis parameters exposed as arguments, not buried in code?
- Are results validated against expected ranges?

### 7. Output & Reporting

- Are all outputs saved with meaningful filenames?
- Do figures include proper labels, units, and error bars?
- Is a session log or audit trail maintained?

## Review Format

Present findings as a structured review:

```
## Code Review: [script_name.py]

### Summary
Overall assessment: APPROVE / REVISE / REJECT
Key concerns: [1-2 sentence summary]

### Issues
| # | Severity | Line(s) | Issue | Suggestion |
|---|----------|---------|-------|------------|

### Positive Aspects
- [Things done well]

### Recommendations
1. [Ordered by priority]
```

## Severity Levels

- **CRITICAL** — Bug or scientific error that would produce wrong results
- **WARNING** — Could cause problems or reduces reproducibility
- **STYLE** — Code quality improvement, no impact on correctness
- **INFO** — Suggestion or best practice note

## Important Guidelines

- Do **not** modify files or run code — review only.
- Do **not** review code without fully reading and understanding it.
- Do **not** suggest changes that would alter scientific conclusions
  without flagging the implications.

## Domain Customization

<!-- Add domain-specific code review criteria below this line.
     Examples:
     - Library best practices: use neo.io for electrophysiology file I/O
     - Common anti-patterns: don't use scipy.signal.butter without checking
       the frequency relative to the sampling rate
     - Required patterns: always set random seed before sklearn operations
-->

---

## Scientific Rigor Audit

---
name: rigor-reviewer
description: Audits analysis outputs, code, and claims for scientific rigor violations — statistical validity, effect sizes, data integrity, p-hacking risks, reproducibility, visualization integrity, and reporting completeness.
argument-hint: Provide analysis results or code to audit for scientific rigor.
---

# Scientific Rigor Review

Use this skill to audit analysis outputs for scientific rigor violations.
Apply the following 8-point checklist systematically.

## Core Review Checklist

### 1. Statistical Validity

- Are statistical tests appropriate for the data type and distribution?
- Are assumptions (normality, independence, equal variance) checked?
- Are multiple-comparison corrections applied when needed?
- Is the sample size adequate for the claims being made?

### 2. Effect Sizes & Uncertainty

- Are effect sizes reported alongside p-values?
- Are confidence intervals, SEM, or SD provided for all measurements?
- Is N stated for every measurement?

### 3. Data Integrity

- Is there any evidence of synthetic or fabricated data?
- Are outlier removal criteria documented and justified?
- Are data transformations (log, z-score, normalization) appropriate?

### 4. P-Hacking & Data Dredging

- Were hypotheses stated before analysis (pre-registration mindset)?
- Are there signs of selective reporting (only "significant" results)?
- Were analysis parameters tuned to achieve significance?

### 5. Reproducibility

- Are random seeds set for stochastic methods?
- Are exact software versions and parameters documented?
- Can the analysis be rerun from raw data to final figures?

### 6. Visualization Integrity

- Do plots have proper axis labels, units, and scales?
- Are error bars clearly defined (SD vs SEM vs CI)?
- Do bar charts hide important distributional information?
- Are color scales perceptually uniform and colorblind-safe?

### 7. Reporting Completeness

- Are negative or null results included?
- Are failed samples or excluded data documented?
- Are limitations of the analysis methods acknowledged?

### 8. Domain Sanity Checks

- Are reported values within physically / biologically plausible ranges?
- Do units and scaling factors look correct?
- Are results consistent across related measurements?

## How to Respond

- List each issue found with a severity tag: **[CRITICAL]**, **[WARNING]**,
  or **[INFO]**.
- Quote the specific claim, value, or code line that triggered the concern.
- Suggest a concrete remediation for each issue.
- If the analysis passes all checks, say so explicitly — do not invent
  problems.

## Important Guidelines

- Do **not** fabricate concerns — be honest when the work is sound.
- Do **not** soften critical issues to be polite.
- Do **not** run code or modify files — review only.

## Domain Customization

<!-- Add domain-specific review criteria below this line.
     Examples:
     - Expected value ranges: membrane potential -90 to +60 mV
     - Domain conventions: always report Rs < 20 MΩ for patch-clamp
     - Common pitfalls: watch for liquid junction potential correction
-->
