# Standard Workflows

This document defines the standard analysis workflows for your agent.
Each workflow is a step-by-step procedure that guides the agent (and the
user) through a common analysis task from start to finish.

> **Tip:** Workflows help the agent choose the right sequence of tools and
> checks for a given task. They also serve as documentation for users
> who want to understand what the agent does and why.

---

## Workflow Overview

<!replace --- A table summarising your workflows. Columns: Workflow, Purpose, Key Steps --- or add a link--->

| Workflow | Purpose | Key Steps |
|----------|---------|-----------|
| *workflow_name* | *purpose* | *key steps* |

---

<!-- REPEAT: workflow_section — One section per workflow. Copy this block for each standard workflow. -->

## <!replace --- The workflow's name, e.g. "Initial Quality Control", "Standard Analysis", "Batch Processing" --- or add a link--->

**Purpose**: <!replace --- A sentence describing when and why to use this workflow --- or add a link--->

**When to Use**:
<!replace --- Conditions or trigger phrases for this workflow --- or add a link--->

### Steps

<!replace --- Numbered steps with sub-steps where needed. Be specific about which tools to call and what to check at each step --- or add a link--->

### Parameters

<!replace --- Key parameters used in this workflow and their defaults --- or add a link--->

### Expected Outputs

<!replace --- What the user should expect at the end of this workflow --- or add a link--->

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
