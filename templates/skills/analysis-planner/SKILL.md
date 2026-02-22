---
name: analysis-planner
description: >-
  Creates step-by-step analysis plans for scientific data — designs the
  pipeline, specifies parameters, anticipates risks, and defines success
  criteria before any code is executed.
argument-hint: Describe your data and research question to get an analysis plan.
---

# Analysis Planning

Use this skill when you need to design a scientific analysis pipeline
before writing or running any code. The planning phase ensures a sound
methodology before committing to implementation.

## Planning Methodology

Follow these steps in order:

### 1. Understand the Question

- Restate the user's research question in your own words.
- Confirm any ambiguities before proceeding.

### 2. Survey the Data

- Examine available files, column names, units, and sample sizes.
- Note missing data, unexpected formats, or potential quality issues.

### 3. Design the Pipeline

Lay out each analysis step in order:

1. Data loading & parsing
2. Quality control checks (missing values, outliers, distributions)
3. Data transformations (normalization, filtering, alignment)
4. Primary analysis (statistical tests, model fitting, feature extraction)
5. Validation & sanity checks
6. Visualization & reporting

### 4. Specify Parameters

For each step, recommend:

- Which library / function to use
- Default parameter values with justification
- Expected output format and value ranges

### 5. Anticipate Risks

Flag potential pitfalls:

- What could go wrong at each step?
- What would invalidate the analysis?
- What fallback approaches exist?

### 6. Define Success Criteria

- What does a "good" result look like?
- How will you know the analysis worked correctly?

## Incremental Execution Principle

Always plan for **incremental validation**:

1. **Examine structure** — load one representative file / sample first
2. **Validate on one** — run the full pipeline on a single sample
3. **Small batch test** — process 2–3 additional units, check consistency
4. **Scale** — only after steps 1–3 pass, process the full dataset

## Output Format

Present the plan as a numbered checklist with clear deliverables at each
step. Include:

- **Step name** — concise label
- **Action** — what to do
- **Tool / library** — which package to use
- **Expected output** — what the result should look like
- **Checkpoint** — how to verify the step succeeded

## Domain Customization

<!-- Add domain-specific planning guidance below this line.
     Examples:
     - Standard pipelines: electrophysiology data always needs filtering before analysis
     - Required steps: always compute input resistance before proceeding
     - Common parameters: typical bandpass filter 0.1–5000 Hz for extracellular recordings
-->
