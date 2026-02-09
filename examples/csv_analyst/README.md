# CSV Analyst — Minimal sciagent Example

A tiny agent that demonstrates how to build a domain-specific scientific
coding assistant on top of the **sciagent** framework.

## Files

| File | Purpose |
|------|---------|
| `config.py` | `AgentConfig` with branding, bounds, suggestions |
| `agent.py` | `CSVAnalyst(BaseScientificAgent)` — ~50 lines |
| `__main__.py` | CLI / Web entry point |

## Quick Start

```bash
# Install sciagent with all extras
pip install -e "../../[cli,web]"

# Install this example's extra deps
pip install pandas seaborn

# Run CLI mode
python -m examples.csv_analyst

# Run Web UI mode
python -m examples.csv_analyst --web
```

## What You Get For Free

By subclassing `BaseScientificAgent` you inherit:

- **Code sandbox** with guardrail scanning & script archiving
- **Guardrails** — CodeScanner, BoundsChecker, data validation
- **Web UI** — branded chat with WebSocket streaming, file upload, figures
- **CLI** — REPL with Rich markdown, slash commands, history
- **MCP server** — JSON-RPC stdio transport for tool exposure
