# Skills

This document provides an overview of the skills available to your agent.
Each skill represents a coherent set of capabilities the agent can apply to
a specific type of analysis task.

> **Tip:** Skills are a way to organise your agent's expertise into
> discoverable, trigger-able units.  They follow the
> [Agent Skills](https://agentskills.io/) open standard and work in
> VS Code Copilot, Copilot CLI, and the Copilot coding agent.
>
> Skills can be used **alongside or instead of** custom agents.  Agents
> provide persona-based workflows with tools and handoffs; skills provide
> procedural capabilities loaded on-demand.

## Default Skills

SciAgent ships 6 default skills in `templates/skills/`.  Copy them into
`.github/skills/` in your workspace to activate them.

| Skill | Location | Description | Slash Command |
|-------|----------|-------------|---------------|
| Scientific Rigor | `skills/scientific-rigor/` | Mandatory rigor principles — data integrity, objectivity, uncertainty, reproducibility | *(auto-loads)* |
| Analysis Planner | `skills/analysis-planner/` | Step-by-step analysis planning with incremental validation | `/analysis-planner` |
| Data QC | `skills/data-qc/` | Systematic data quality control checklist with severity-rated reporting | `/data-qc` |
| Rigor Reviewer | `skills/rigor-reviewer/` | 8-point scientific rigor audit checklist | `/rigor-reviewer` |
| Report Writer | `skills/report-writer/` | Publication-quality report generation template and guidelines | `/report-writer` |
| Code Reviewer | `skills/code-reviewer/` | 7-point code review checklist for scientific scripts | `/code-reviewer` |

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

1. Create a new directory for the skill: `.github/skills/<skill_name>/`
2. Add a `SKILL.md` with YAML frontmatter and instructions
3. Update this document with the new skill

### SKILL.md Template

```markdown
---
name: skill-name
description: Description of what the skill does and when to use it (max 1024 chars)
argument-hint: Hint text shown when invoked via /slash command
---

# Skill Name

## When to Use
- Trigger condition 1
- Trigger condition 2

## Procedure
### Step 1
Details...

### Step 2
Details...

## Examples
### Example 1
Expected input and output

## Domain Customization
<!-- Add domain-specific guidance below this line. -->
```

### Skill vs Agent — When to Choose Which

| Use a **Skill** when... | Use an **Agent** when... |
|------------------------|------------------------|
| You want on-demand procedural guidance | You need a distinct persona with tool restrictions |
| The capability is self-contained | You need handoff workflows between roles |
| You want portability across Copilot, CLI, and coding agent | You need Claude Code compatibility via `.claude/agents/` |
| The instructions augment any active agent | The instructions replace the default agent behavior |

You can also use **both** — install agents for workflow handoffs and skills
for ad-hoc capabilities.  The `scientific-rigor` skill auto-loads to
supplement any agent with rigor principles.
