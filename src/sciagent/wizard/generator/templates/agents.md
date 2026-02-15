# Agents

This document defines the sub-agents available in your agent. Each agent is
specialized for a particular aspect of your domain's analysis.

> **Tip:** Not every agent needs sub-agents. If your domain is narrow enough
> that a single agent covers everything, you can delete this file or keep
> only the main agent entry.

---

## Overview

<!-- REPLACE: agent_overview_table — A Markdown table listing your sub-agents. Columns: Agent, Role, Primary Skills. Example:
| Agent | Role | Primary Skills |
|-------|------|----------------|
| main-analyst | Main coordinator | All skills |
| data-loader | Data import specialist | file_loading |
| qc-checker | Quality control specialist | quality_control |
-->

| Agent | Role | Primary Skills |
|-------|------|----------------|
| *your-main-agent* | Main coordinator | All skills |

---

## Main Agent

**Role**: Primary analysis coordinator

**Description**: The main analysis agent. Orchestrates workflows, delegates
to specialist sub-agents when appropriate, and provides comprehensive
interpretations.

**Capabilities**:
- Full access to all tools and skills
- Workflow orchestration (e.g., QC → analysis → interpretation)
- Result interpretation with domain context

**When to Use**: Default agent for general analysis requests.

---

<!-- REPEAT: agent_section — One section per sub-agent. Copy this block and fill in the fields for each specialist agent you want to define. -->

## <!-- REPLACE: agent_name — The sub-agent's slug name, e.g. "spike-analyst", "qc-checker" -->

**Role**: <!-- REPLACE: agent_role — A short role title, e.g. "Action potential specialist", "Quality control specialist" -->

**Description**: <!-- REPLACE: agent_description — A sentence or two describing what this agent does and when it's useful. Example: "Expert in detecting and characterizing action potentials. Analyzes firing patterns, extracts spike features, and interprets neuronal excitability." -->

**Capabilities**:
<!-- REPLACE: agent_capabilities — A bullet list of specific capabilities. Example:
- Spike detection with configurable thresholds
- Individual AP feature extraction (threshold, amplitude, width)
- Firing pattern classification
-->

**When to Use**:
<!-- REPLACE: agent_when_to_use — Trigger phrases or situations where this agent should be invoked. Example:
- "Detect spikes in this trace"
- "What's the firing rate?"
- "Analyze the action potential features"
-->

---

<!-- END_REPEAT -->

## Adding Custom Agents

To add a custom agent:

1. Define the agent configuration in your agent module
2. Create a system message for the agent's speciality
3. Document the agent in this file following the template above

```python
# Example agent definition
CUSTOM_AGENT = {
    "name": "custom-analyst",
    "display_name": "Custom Analysis Agent",
    "description": "Description of the agent's role",
    "skills": ["skill1", "skill2"],
}
```
