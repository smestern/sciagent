# SciAgent — Default Agents

Ready-to-use agent files for **VS Code GitHub Copilot** and **Claude Code**.

## Quick Start

Copy the folders you need into your workspace root:

```bash
# VS Code Copilot custom agents
cp -r templates/agents/.github/  /path/to/your/workspace/

# Claude Code sub-agents
cp -r templates/agents/.claude/  /path/to/your/workspace/

# Or both
cp -r templates/agents/.github/ templates/agents/.claude/ /path/to/your/workspace/
```

Open VS Code — the agents appear in the **Agents dropdown** in Copilot Chat.

## Included Agents

| Agent | Role | Mode |
|-------|------|------|
| `analysis-planner` | Design analysis roadmap (read-only) | Planning |
| `data-qc` | Check data quality before analysis | QC |
| `rigor-reviewer` | Audit results for scientific rigor (read-only) | Review |
| `report-writer` | Generate structured reports | Reporting |
| `code-reviewer` | Review scripts for correctness (read-only) | Review |

## Handoff Workflow

The agents are wired together via handoff buttons:

```
Planner → Data QC → (your domain agent) → Rigor Reviewer → Report Writer
```

Code Reviewer is standalone — invoke it on any script at any time.

## Customization

Each agent file has a `## Domain Customization` section near the bottom.
Add your domain-specific knowledge there (expected value ranges, domain
terminology, common analysis patterns, etc.).

## Documentation

See [docs/copilot-agents.md](../docs/copilot-agents.md) for the full guide.
