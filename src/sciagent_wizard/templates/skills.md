# Skills

This document provides an overview of the skills available to your agent.
Each skill represents a coherent set of capabilities the agent can apply to
a specific type of analysis task.

> **Tip:** Skills are a way to organise your agent's expertise into
> discoverable, trigger-able units. Not every agent needs multiple skills —
> a single "general analysis" skill may be sufficient for simpler domains.

## Skill Overview

<!-- REPLACE: skills_overview_table — A Markdown table listing your agent's skills. Columns: Skill, Location, Description. Example:
| Skill | Location | Description |
|-------|----------|-------------|
| Data Loading | skills/data_loading/ | File parsing and format detection |
| Quality Control | skills/quality_control/ | Data quality assessment |
| Feature Extraction | skills/feature_extraction/ | Extracting measurements from raw data |
| Visualisation | skills/visualisation/ | Generating plots and figures |
-->

| Skill | Location | Description |
|-------|----------|-------------|
| *skill_name* | *path* | *brief description* |

---

<!-- REPEAT: skill_section — One section per skill. Copy this block for each skill your agent supports. -->

## <!-- REPLACE: skill_name — The skill's display name, e.g. "Spike Analysis", "Quality Control" -->

**File**: <!-- REPLACE: skill_file_path — Path to the skill definition file, e.g. "skills/spike_analysis/SKILL.md" -->

**Purpose**: <!-- REPLACE: skill_purpose — One sentence describing the skill's purpose. Example: "Detect and analyze action potentials in current-clamp recordings." -->

**Key Capabilities**:
<!-- REPLACE: skill_capabilities — A bullet list of specific capabilities. Example:
- Threshold-based event detection
- Individual event feature extraction (amplitude, duration, kinetics)
- Event train analysis (adaptation, intervals, statistics)
- Rate-response curve construction
-->

**Trigger Keywords**: <!-- REPLACE: skill_trigger_keywords — Comma-separated keywords or phrases that should activate this skill. Example: "spike, action potential, firing, threshold, rheobase, detection" -->

---

<!-- END_REPEAT -->

## Adding New Skills

1. Create a new directory for the skill: `skills/<skill_name>/`
2. Add a `SKILL.md` with the skill definition
3. Update this document with the new skill

### Skill File Template

```markdown
# Skill Name

## Description
Brief description of the skill's purpose.

## When to Use
- Trigger condition 1
- Trigger condition 2

## Capabilities
### Capability 1
Details...

### Capability 2
Details...

## Tools Used
- tool_1
- tool_2

## Example Workflows
### Workflow 1
```
1. Step 1
2. Step 2
```

## Parameters Reference
| Parameter | Default | Description |
|-----------|---------|-------------|
| param1    | value   | description |

## Notes
Additional information...
```
