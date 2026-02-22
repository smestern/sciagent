---
name: code-reviewer
description: >-
  Reviews scientific analysis scripts for correctness, reproducibility,
  error handling, code quality, performance, and scientific best practices —
  provides severity-rated actionable feedback without modifying code.
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
