# SciAgent — Scientific Analysis Agents for GitHub Copilot

> **9 specialized agents** and **9 skills** that bring scientific rigor
> to data analysis in VS Code. Plan experiments, check data quality, write
> reproducible code, audit results, and generate publication-ready reports —
> all with built-in guardrails against p-hacking, data fabrication, and
> irreproducible workflows.

**Version**: 1.2.0 | **License**: MIT | **Author**: [smestern](https://github.com/smestern)

## Why SciAgent?

Scientific coding is different from software engineering. A subtle off-by-one
in a loop isn't just a bug — it's a retracted paper. SciAgent embeds
**8 rigor principles** directly into every agent:

1. **Data Integrity** — never fabricate or fill gaps with synthetic data
2. **Objective Analysis** — reveal what data shows, not what you hope
3. **Sanity Checks** — validate inputs, flag impossible values
4. **Transparent Reporting** — report all results, even inconvenient ones
5. **Uncertainty Quantification** — confidence intervals, SEM, N for everything
6. **Reproducibility** — deterministic code, documented seeds, exact parameters
7. **Safe Execution** — analysis runs through guardrailed tools, not raw shell
8. **Rigor Warnings** — surface warnings to the user, never silently suppress

## Installation

### From Awesome Copilot Marketplace

```bash
copilot plugin marketplace add github/awesome-copilot
copilot plugin install sciagent@awesome-copilot
```

### Manual (VS Code)

Clone this repo and add to your VS Code settings:

```jsonc
// settings.json
"chat.plugins.paths": {
    "/path/to/sciagent-plugin": true
}
```

## Agents

| Agent | Description |
|-------|-------------|
| `@sciagent-analysis-planner` | Designs step-by-step analysis plans before any code runs |
| `@sciagent-code-reviewer` | Reviews scripts for correctness, reproducibility, and best practices |
| `@sciagent-coder` | Implements analysis code with built-in rigor enforcement |
| `@sciagent-coordinator` | Routes tasks to the right specialist agent |
| `@sciagent-data-qc` | Checks data quality — missing values, outliers, distributions, integrity |
| `@sciagent-docs-ingestor` | Ingests Python library docs into structured API references |
| `@sciagent-domain-assembler` | Configures SciAgent for your specific research domain |
| `@sciagent-report-writer` | Generates publication-quality reports with uncertainty quantification |
| `@sciagent-rigor-reviewer` | Audits analysis for statistical validity and reproducibility |

## Skills

| Skill | Description |
|-------|-------------|
| `/analysis-planner` | On-demand analysis planner |
| `/code-reviewer` | On-demand code reviewer |
| `/configure-domain` | On-demand configure domain |
| `/data-qc` | On-demand data qc |
| `/docs-ingestor` | On-demand docs ingestor |
| `/report-writer` | On-demand report writer |
| `/rigor-reviewer` | On-demand rigor reviewer |
| `/scientific-rigor` | On-demand scientific rigor |
| `/update-domain` | On-demand update domain |

## Typical Workflow

```
You: @sciagent-coordinator I have calcium imaging data in traces.csv.
     Find responsive neurons and characterize their response profiles.

Coordinator → Analysis Planner → Data QC → Coder → Rigor Reviewer → Report Writer
```

Each agent hands off to the next, enforcing rigor at every step. The final
output is a structured report with figures, statistics, and reproducibility
metadata.

## Customization

SciAgent works out of the box for general scientific analysis. To specialize
for your research domain (e.g., electrophysiology, genomics, ecology), use
the `/configure-domain` skill which discovers relevant Python packages and
tailors agent behavior to your field.

## Framework

This plugin is generated from the [SciAgent framework](https://github.com/smestern/sciagent),
which also provides a Python SDK, CLI, and full-stack web interface for
building custom scientific analysis agents.

## License

MIT
