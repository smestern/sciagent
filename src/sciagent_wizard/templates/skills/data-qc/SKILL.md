---
name: data-qc
description: >-
  Performs systematic data quality control checks before analysis — missing
  values, outliers, distributions, unit validation, duplicates, and
  structural integrity assessment with severity-rated reporting.
argument-hint: Provide your dataset to run quality control checks.
---

# Data Quality Control

Use this skill when you need to assess data quality before performing
any analysis. Run these checks systematically for every dataset.

## QC Checklist

### 1. Structural Integrity

- Can the file be loaded without errors?
- Are column names / headers present and correct?
- Is the data shape (rows × columns) as expected?
- Are data types correct (numeric vs string vs datetime)?

### 2. Missing Data

- Count and percentage of missing values per column.
- Pattern of missingness — random or systematic?
- Are missing values coded correctly (NaN, -999, empty string, etc.)?
- Recommendation: impute, exclude, or flag?

### 3. Outliers & Anomalies

- Identify values outside expected ranges (use domain bounds if available).
- Check for impossible values (negative concentrations, pressures < 0, etc.).
- Look for suspicious patterns: constant values, perfect sequences, sudden jumps.
- Use IQR or z-score methods as appropriate.

### 4. Distributions

- Compute summary statistics (mean, median, SD, min, max) for each numeric column.
- Check for normality where relevant (Shapiro-Wilk, Q-Q plots).
- Identify skewness or multimodality.
- Flag zero-variance columns.

### 5. Units & Scaling

- Verify units are consistent within columns.
- Check for mixed unit systems (e.g. mV and V in the same column).
- Look for off-by-factor errors (×1000, ×1e6).

### 6. Duplicates & Consistency

- Check for duplicate rows or IDs.
- Verify relational consistency (e.g. timestamps are monotonic).
- Cross-validate related columns (e.g. start < end).

## Reporting Format

Present QC results as a structured report:

```
## Data QC Report

### Summary
- Files checked: N
- Total records: N
- Overall quality: PASS / WARN / FAIL

### Issues Found
| # | Severity | Column/Field | Issue | Recommendation |
|---|----------|-------------|-------|----------------|

### Column Statistics
| Column | Type | N | Missing | Min | Max | Mean | SD |
|--------|------|---|---------|-----|-----|------|-----|
```

## Severity Levels

- **CRITICAL** — Data cannot be analysed without fixing this
- **WARNING** — Analysis can proceed but results may be affected
- **INFO** — Notable but not problematic

## Important Guidelines

- Do **not** silently fix data issues — always report them first.
- Do **not** remove outliers without documenting the criteria.
- After QC is complete, hand off findings before proceeding to primary analysis.

## Domain Customization

<!-- Add domain-specific QC criteria below this line.
     Examples:
     - Expected ranges: holding current should be -500 to +500 pA
     - Required checks: verify sampling rate matches expected value (e.g. 20 kHz)
     - Common issues: watch for 60 Hz line noise in electrophysiology recordings
-->
