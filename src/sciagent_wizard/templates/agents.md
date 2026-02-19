# Default Scientific Agents

SciAgent ships five **domain-agnostic** agents that implement common
scientific workflow roles.  They work out of the box for any research
domain and include clearly marked **extension points** where you inject
your own domain-specific knowledge.

Copy the ready-to-use files from [`agents/`](../agents/) into your
workspace, or use the Python presets in `sciagent.agents`.

---

## Overview

| Agent | Role | Tools (VS Code) | Handoff |
|-------|------|-----------------|---------|
| `analysis-planner` | Design the analysis roadmap | codebase, search, fetch | → `data-qc` |
| `data-qc` | Check data quality before analysis | codebase, terminal, editFiles, search | → *(your domain agent)* |
| `rigor-reviewer` | Audit results for scientific rigor | codebase, search, fetch | → `report-writer` |
| `report-writer` | Generate structured reports | codebase, editFiles, search, fetch | *(end)* |
| `code-reviewer` | Review scripts for correctness | codebase, search | *(standalone)* |

### Handoff Workflow

```
┌──────────────────┐     ┌──────────┐     ┌─────────────────────┐
│ Analysis Planner │ ──► │ Data QC  │ ──► │ Your Domain Agent   │
└──────────────────┘     └──────────┘     └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Rigor Reviewer     │
                                          └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Report Writer      │
                                          └─────────────────────┘

         Code Reviewer ◄── invoke standalone on any script
```

---

## Analysis Planner

**Role**: Analysis roadmap designer

**Description**: Creates step-by-step analysis plans before any code runs.
Surveys available data, designs the pipeline, specifies parameters, and
anticipates risks.  Read-only — never executes code.

**Tools**: `codebase`, `search`, `fetch` (read-only)

**Capabilities**:
- Restate research questions and confirm ambiguities
- Survey data files, columns, units, and sample sizes
- Design ordered analysis pipelines with parameter recommendations
- Apply the incremental execution principle (1 sample → small batch → full)
- Anticipate risks and define success criteria

**Handoff**: → `data-qc` ("Run quality checks on this data")

**Extension Points**:
Add domain-specific workflow steps, common experimental designs, and
standard analysis pipelines in the `## Domain Customization` section.

---

## Data QC Specialist

**Role**: Data quality gatekeeper

**Description**: Thoroughly assesses data quality before analysis proceeds.
Runs QC checks, produces a structured report with severity-tagged issues.

**Tools**: `codebase`, `terminal`, `editFiles`, `search` (full access for QC)

**Capabilities**:
- Structural integrity checks (file loading, column types, shape)
- Missing data analysis (counts, patterns, recommendations)
- Outlier detection (IQR, z-score, domain bounds)
- Distribution assessment (normality, skew, zero-variance)
- Unit consistency and scaling validation
- Duplicate and relational consistency checks

**Handoff**: → your domain agent ("Data passes QC, proceed with analysis")

**Extension Points**:
Add expected column names, plausible value ranges, file format notes,
and domain-specific QC thresholds in the `## Domain Customization` section.

---

## Scientific Rigor Reviewer

**Role**: Post-analysis rigor auditor

**Description**: Reviews analysis outputs, code, and claims for violations
of scientific best practice.  Does not run analyses — reviews what others
have produced.

**Tools**: `codebase`, `search`, `fetch` (read-only)

**Capabilities**:
- Statistical validity checks (appropriate tests, assumptions, corrections)
- Effect size and uncertainty reporting verification
- Data integrity auditing (no synthetic data, documented outlier removal)
- P-hacking and selective reporting detection
- Reproducibility assessment (seeds, versions, parameters)
- Visualization integrity (labels, error bars, colorblind safety)

**Handoff**: → `report-writer` ("Results pass rigor review, generate report")

**Extension Points**:
Add domain-specific value ranges, conventions, and common pitfalls in
the `## Domain Customization` section.

---

## Report Writer

**Role**: Publication-quality report generator

**Description**: Synthesises analysis results into structured Markdown
reports with figures, tables, uncertainty quantification, and
reproducibility information.

**Tools**: `codebase`, `editFiles`, `search`, `fetch`

**Capabilities**:
- Generate structured reports (abstract, methods, results, limitations)
- Ensure uncertainty is reported for all quantitative claims
- Reference figures with proper captions and labelling standards
- Link to reproducible scripts
- Include negative results and limitations

**Handoff**: *(end of workflow)*

**Extension Points**:
Add required report sections, journal style preferences, and domain
terminology in the `## Domain Customization` section.

---

## Code Reviewer

**Role**: Script correctness auditor

**Description**: Reviews analysis scripts for correctness, reproducibility,
and adherence to best practices.  Provides actionable feedback without
modifying code.  Standalone — invoke on any script at any time.

**Tools**: `codebase`, `search` (read-only)

**Capabilities**:
- Correctness checks (computations, edge cases, indexing)
- Reproducibility assessment (seeds, hardcoded paths, determinism)
- Error handling review
- Code quality evaluation (naming, documentation, organization)
- Performance suggestions (vectorization, memory management)
- Scientific best practice adherence

**Handoff**: *(standalone — no default handoff)*

**Extension Points**:
Add domain-specific library best practices and common anti-patterns in
the `## Domain Customization` section.

---

## Adding Domain-Specific Agents

These five agents cover common scientific workflow roles.  For
domain-specific specialists (e.g. a spike-analysis agent for
electrophysiology), add a new agent following the same pattern:

1. **Python preset**: Create a module in `src/sciagent/agents/` with an
   `AgentConfig` and prompt string
2. **VS Code agent**: Add a `.agent.md` file to `.github/agents/`
3. **Claude agent**: Add a `.md` file to `.claude/agents/`
4. **Wire handoffs**: Add `handoffs` entries in the YAML frontmatter

Or use the self-assembly wizard (`sciagent wizard -m copilot_agent`) to
generate domain-specific agents automatically from a conversation.

```python
from sciagent.agents import get_agent_config

# Load a default agent preset
rigor = get_agent_config("rigor-reviewer")

# Or import all defaults
from sciagent.agents import ALL_DEFAULT_AGENTS
for name, cfg in ALL_DEFAULT_AGENTS.items():
    print(f"{name}: {cfg.display_name}")
```
