---
name: report-writer
description: >-
  Generates structured scientific reports from analysis results — publication-
  quality Markdown with abstract, methods, results, figures, tables, uncertainty
  quantification, limitations, and reproducibility information.
argument-hint: Provide analysis results to generate a structured scientific report.
---

# Scientific Report Writing

Use this skill when synthesising analysis results into a structured
scientific report document.

## Report Structure

Generate reports following this template:

### Title

### Abstract / Summary

Brief overview of the analysis, key findings, and conclusions.

### Methods

- Data source and acquisition details
- Analysis pipeline description
- Software, libraries, and versions used
- Key parameters and their justification

### Results

For each result section:

- Quantitative findings with uncertainty (mean ± SD, 95% CI)
- N for every measurement
- Statistical test results (test name, statistic, p-value, effect size)
- Reference to figures and tables

### Figures

- Properly labelled axes with units
- Error bars defined (SD, SEM, or CI — specify which)
- Colorblind-safe palettes
- Each figure has a caption explaining what it shows

### Tables

- Summary statistics with appropriate precision
- All columns labelled with units
- N stated for each group

### Limitations

- Known issues with the data or analysis
- Assumptions that may not hold
- Suggested follow-up analyses

### Reproducibility

- Link to the reproducible script
- Random seeds used
- Software environment details

## Writing Guidelines

1. **Precision** — Report values with appropriate significant figures.
   Do not over-report precision beyond what the measurement supports.

2. **Uncertainty is mandatory** — Every quantitative claim must include
   an uncertainty estimate (SD, SEM, CI, or IQR as appropriate). State
   N for every measurement.

3. **Honest reporting** — Include negative results, failed analyses, and
   unexpected findings. Do not cherry-pick.

4. **Active voice, past tense** for methods and results.
   Present tense for established facts and conclusions.

5. **Units always** — Every number should have units.

6. **Figures tell the story** — Reference figures inline. Every figure
   must have a caption.

## Important Guidelines

- Do **not** fabricate or embellish results.
- Do **not** omit negative findings or failed analyses.
- Do **not** over-interpret results beyond what the data supports.

## Domain Customization

<!-- Add domain-specific reporting guidance below this line.
     Examples:
     - Required sections: always include input resistance and resting Vm
     - Journal style: follow Journal of Neuroscience formatting guidelines
     - Domain terminology: use "action potential" not "spike" in formal reports
     - Standard figures: always include I-V curve and time series trace
-->
