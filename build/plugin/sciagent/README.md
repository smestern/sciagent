# SciAgent — Copilot Agent Plugin

Scientific analysis agents with built-in rigor enforcement for GitHub Copilot.

**Version**: 1.1.0

## Installation

### Local (development)

Clone or download this plugin directory, then add it to your VS Code settings:

```jsonc
// settings.json
"chat.plugins.paths": {
    "/path/to/sciagent": true
}
```

### From marketplace

If published to a plugin marketplace repository, install via the Extensions
sidebar → Agent Plugins view, or search `@agentPlugins sciagent`.

## Agents

| Agent | Invocation |
|-------|------------|
| sciagent-analysis-planner | `@sciagent-analysis-planner` |
| sciagent-code-reviewer | `@sciagent-code-reviewer` |
| sciagent-data-qc | `@sciagent-data-qc` |
| sciagent-docs-ingestor | `@sciagent-docs-ingestor` |
| sciagent-domain-assembler | `@sciagent-domain-assembler` |
| sciagent-report-writer | `@sciagent-report-writer` |
| sciagent-rigor-reviewer | `@sciagent-rigor-reviewer` |
| sciagent-Sciagent | `@sciagent-Sciagent` |

## Skills

| Skill | Slash Command |
|-------|---------------|
| analysis-planner | `/analysis-planner` |
| code-reviewer | `/code-reviewer` |
| configure-domain | `/configure-domain` |
| data-qc | `/data-qc` |
| docs-ingestor | `/docs-ingestor` |
| report-writer | `/report-writer` |
| rigor-reviewer | `/rigor-reviewer` |
| scientific-rigor | `/scientific-rigor` |
| update-domain | `/update-domain` |

## What's Included

- **6 specialized agents** for scientific analysis workflows: planning,
  data QC, code review, rigor auditing, report writing, and documentation
  ingestion.
- **7 skills** providing on-demand expertise: scientific rigor enforcement,
  analysis planning, data QC checklists, rigor review, report templates,
  code review, and library documentation ingestion.
- **Built-in scientific rigor principles** inlined into every agent —
  data integrity, objective analysis, sanity checks, transparent reporting,
  uncertainty quantification, and reproducibility.

## Source

This plugin is generated from the [SciAgent](https://github.com/smestern/sciagent)
framework templates.

## License

MIT
