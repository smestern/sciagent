# Standard Workflows

This document defines the standard analysis workflows for your agent.
Each workflow is a step-by-step procedure that guides the agent (and the
user) through a common analysis task from start to finish.

> **Tip:** Workflows help the agent choose the right sequence of tools and
> checks for a given task. They also serve as documentation for users
> who want to understand what the agent does and why.

---

## Workflow Overview

<!-- REPLACE: workflow_overview_table — A table summarising your workflows. Columns: Workflow, Purpose, Key Steps. Example:
| Workflow | Purpose | Key Steps |
|----------|---------|-----------|
| Initial QC | Assess data quality before analysis | Load → inspect → validate → report |
| Standard Analysis | Core measurement extraction | QC → detect → extract → summarise |
| Comparative | Compare across conditions/groups | Load all → match → analyse → statistics |
| Export | Package results for publication | Collect → format → figures → export |
-->

| Workflow | Purpose | Key Steps |
|----------|---------|-----------|
| *workflow_name* | *purpose* | *key steps* |

---

<!-- REPEAT: workflow_section — One section per workflow. Copy this block for each standard workflow. -->

## <!-- REPLACE: workflow_name — The workflow's name, e.g. "Initial Quality Control", "Standard Analysis", "Batch Processing" -->

**Purpose**: <!-- REPLACE: workflow_purpose — A sentence describing when and why to use this workflow. Example: "Assess recording quality before committing to a full analysis run." -->

**When to Use**:
<!-- REPLACE: workflow_when_to_use — Conditions or trigger phrases for this workflow. Example:
- User provides a new data file
- User asks "check the quality" or "is this data usable?"
- Before any substantive analysis
-->

### Steps

<!-- REPLACE: workflow_steps — Numbered steps with sub-steps where needed. Be specific about which tools to call and what to check at each step. Example:

```
1. Load file metadata (use get_file_metadata)
   - Report file type, dimensions, key metadata
   - Check file is a supported format

2. Run quality control checks (use run_qc)
   - Check for missing values, NaN, Inf
   - Measure noise / baseline stability
   - Flag any anomalies

3. Validate value ranges
   - Compare key measurements against expected bounds
   - Flag out-of-range values with warnings

4. Generate QC report
   - Summarise pass/fail status for each check
   - Recommend whether to proceed or exclude
   - Ask user for confirmation if issues found
```
-->

### Parameters

<!-- REPLACE: workflow_parameters — Key parameters used in this workflow and their defaults. Example:
| Parameter | Default | Description |
|-----------|---------|-------------|
| max_noise | 2.0 | Maximum acceptable noise level |
| min_samples | 100 | Minimum number of data points required |
-->

### Expected Outputs

<!-- REPLACE: workflow_outputs — What the user should expect at the end of this workflow. Example:
- QC summary table (pass/fail per check)
- List of flagged issues with severity
- Recommendation: proceed / exclude / review
-->

---

<!-- END_REPEAT -->

## Workflow Selection Guide

When a user's request doesn't map clearly to a single workflow:

1. **Ask** which aspect of the data they want to explore
2. **Suggest** the most relevant workflow based on their description
3. **Default** to the initial QC workflow if the data hasn't been validated yet

### Combining Workflows

Workflows are designed to be composed:

```
Initial QC → Standard Analysis → Export
     ↑              ↑
     └── if issues ─┘ (re-run after fixing)
```

For batch processing, wrap any workflow in a loop over files/samples and
collect results into a summary table.

---

## Customising Workflows

To modify or add workflows:

1. Copy the template section above
2. Fill in each placeholder with your domain-specific steps
3. Reference specific tools by name so the agent knows what to call
4. Include parameter tables so defaults are documented
5. Define expected outputs so the agent knows when the workflow is complete
