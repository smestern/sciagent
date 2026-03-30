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
| `sciagent-coder` | Implement code with scientific rigor | codebase, terminal, editFiles, search | → `rigor-reviewer` |
| `data-qc` | Check data quality before analysis | codebase, terminal, editFiles, search | → `sciagent-coder` |
| `rigor-reviewer` | Audit results for scientific rigor | codebase, search, fetch | → `report-writer` |
| `report-writer` | Generate structured reports | codebase, editFiles, search, fetch | *(end)* |
| `code-reviewer` | Review scripts for correctness | codebase, search | *(standalone)* |
| `domain-assembler` | Configure SciAgent for your domain | codebase, editFiles, search, fetch | → `docs-ingestor` |
| `docs-ingestor` | Learn new library APIs | codebase, search, fetch, terminal | → `analysis-planner` |

### Handoff Workflow

```
┌────────────────────┐
│ Domain Assembler   │ ◄── /configure-domain, /update-domain
└────────┬───────────┘
         │
         ▼
┌──────────────────┐     ┌──────────┐     ┌─────────────────────┐
│ Analysis Planner │ ──► │ Data QC  │ ──► │  Scientific Coder   │
└──────────────────┘     └──────────┘     └─────────┬───────────┘
        ▲                                           │
        │                                 ┌─────────▼───────────┐
┌───────┴──────────┐                      │  Rigor Reviewer     │
│  Docs Ingestor   │                      └─────────┬───────────┘
└──────────────────┘                                │
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

## Scientific Coder

**Role**: General-purpose implementation agent with scientific rigor

**Description**: Writes, edits, and executes code — from utility scripts
to full analysis pipelines.  When working with scientific data, enforces
data integrity, reproducibility, and transparent reporting automatically.
This is the default implementation target for all specialist handoffs.

**Tools**: `codebase`, `terminal`, `editFiles`, `search` (full access)

**Capabilities**:
- Implement analysis plans produced by analysis-planner
- Write and execute scientific analysis code with rigor enforcement
- Follow the incremental execution principle (1 sample → batch → full)
- Validate inputs, sanity-check intermediate values, flag anomalies
- Report uncertainty (CI, SEM, SD) and state N for all measurements
- Produce standalone, reproducible Python scripts with argparse
- Handle general (non-scientific) coding tasks idiomatically

**Handoff**: → `rigor-reviewer` ("Implementation complete, audit rigor")
             → `report-writer` ("Generate report from results")
             → `code-reviewer` ("Review the code")

**Extension Points**:
Add preferred libraries, standard output formats, common analysis
patterns, and expected value ranges in the `## Domain Customization`
section.

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

Or use the self-assembly wizard (`sciagent wizard -m copilot`) to
generate domain-specific agents automatically from a conversation.

---

## Domain Assembler

**Role**: Self-assembly domain configurator

**Description**: Configures SciAgent for your research domain by
interviewing you, discovering relevant scientific packages via PyPI and
GitHub, and creating domain knowledge files in `docs/domains/<slug>/`
with links from the template instruction files.  Supports multiple
domains per workspace with hot-swapping via `/switch-domain`.  No wizard
dependency needed — uses only VS Code's built-in `fetch` and `editFiles`
tools.

**Tools**: `codebase`, `editFiles`, `search`, `fetch`

**Capabilities**:
- Auto-detect unfilled `<!replace ...>` markers (or legacy
  `<!-- REPLACE: ... -->` placeholders) and suggest setup
- Conversational domain interview (data types, packages, workflows, goals)
- Lightweight package discovery via PyPI JSON API and GitHub READMEs
- Create separate domain knowledge files in `docs/domains/<slug>/` and link from templates
- Append custom guardrails, workflows, and skills beyond placeholders
- Create condensed package API references in `docs/domains/<slug>/`
- Incremental updates without re-running the full setup

**Skills**: Exposes three user-invokable skills:
- `/configure-domain` — Full first-time setup (interview → discover → fill → verify)
- `/update-domain` — Incremental updates (add packages, refine workflows)
- `/switch-domain` — Switch between configured domains (hot-swap docs, skills, links)

**Handoff**: → `docs-ingestor` ("Deep-crawl library docs for the
packages identified during assembly")

**Requirements**: None — works with any SciAgent installation.  For
deep documentation crawling, the `docs-ingestor` agent requires
`sciagent[wizard]`.

**Extension Points**:
Add default packages, preferred search queries, and domain-specific
assembly guidance in the `## Domain Customization` section.

---

## Docs Ingestor

**Role**: Library documentation specialist

**Description**: Ingests documentation for any Python library by crawling
PyPI, ReadTheDocs, and GitHub.  Produces a structured API reference
(classes, functions, pitfalls, recipes) that all other agents can consult
via `read_doc()`.  Use this when you need to learn an unfamiliar library
for scientific analysis.

**Tools**: `codebase`, `search`, `fetch`, `terminal` (terminal for `pip install`)

**Capabilities**:
- Check for existing ingested docs before re-crawling
- Deep-crawl PyPI metadata, ReadTheDocs/Sphinx API pages, GitHub source
- LLM-powered extraction of Core Classes, Key Functions, Common Pitfalls,
  and Quick-Start Recipes
- Save structured `<package>_api.md` reference to the docs directory
- Summarise key capabilities for the user after ingestion
- Install missing libraries via terminal (with user confirmation)

**Handoff**: → `analysis-planner` ("Library docs ingested, plan an analysis")

**Requirements**: Requires `sciagent[wizard]` — install with
`pip install sciagent[wizard]`.

**Extension Points**:
Add domain-specific default libraries to ingest, preferred GitHub URLs
for internal packages, and post-ingestion checklist items in the
`## Domain Customization` section.

```python
from sciagent.agents import get_agent_config

# Load a default agent preset
rigor = get_agent_config("rigor-reviewer")

# Or import all defaults
from sciagent.agents import ALL_DEFAULT_AGENTS
for name, cfg in ALL_DEFAULT_AGENTS.items():
    print(f"{name}: {cfg.display_name}")
```
