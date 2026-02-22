# Architecture

An overview of how SciAgent's modules fit together.

---

## System Diagram

```
┌─────────────────────────────────────────┐
│           Your Domain Agent             │
│  (subclass BaseScientificAgent)         │
│  • Domain tools & loaders               │
│  • Domain system prompt                 │
│  • Domain bounds & patterns             │
├─────────────────────────────────────────┤
│              sciagent                   │
│  ┌──────────┐ ┌───────────┐ ┌────────┐ │
│  │ Base     │ │ Guardrails│ │ Data   │ │
│  │ Agent    │ │ Scanner   │ │Resolver│ │
│  │ Config   │ │ Validator │ │ Cache  │ │
│  └──────────┘ │ Bounds    │ └────────┘ │
│  ┌──────────┐ └───────────┘ ┌────────┐ │
│  │ Tools    │ ┌───────────┐ │  MCP   │ │
│  │ Sandbox  │ │  Web UI   │ │ Server │ │
│  │ Fitting  │ │  CLI REPL │ │        │ │
│  │ Registry │ └───────────┘ └────────┘ │
│  └──────────┘                          │
├─────────────────────────────────────────┤
│           GitHub Copilot SDK            │
└─────────────────────────────────────────┘
```

**Your agent** sits on top. It subclasses `BaseScientificAgent`, defines domain-specific tools, and configures guardrails via `AgentConfig`. The **sciagent framework** provides all the infrastructure. The **Copilot SDK** handles the LLM communication layer.

---

## Module Reference

| Module | Package | Description |
|--------|---------|-------------|
| Base Agent | `sciagent.base_agent` | Abstract base class with Copilot SDK session lifecycle |
| Config | `sciagent.config` | `AgentConfig` dataclass for all customization |
| Agents | `sciagent.agents` | Default agent presets (rigor reviewer, planner, QC, report writer, code reviewer) + converter script |
| Prompts | `sciagent.prompts` | Composable system message building blocks (scientific rigor, code execution, communication style, etc.) |
| Guardrails | `sciagent.guardrails` | Code scanner, data validator, bounds checker |
| Tools | `sciagent.tools` | Sandboxed code execution, curve fitting, figure handling, tool registry |
| Data | `sciagent.data` | Base data resolver with format registration & caching |
| CLI | `sciagent.cli` | Rich terminal REPL with slash commands |
| Web | `sciagent.web` | Quart WebSocket chat UI (dark/light theme) |
| MCP | `sciagent.mcp` | MCP JSON-RPC server scaffold (stdio transport) |

---

## Guardrails Pipeline

SciAgent enforces scientific rigor through a 5-layer system:

```
Code submitted for execution
        │
        ▼
┌─────────────────────┐
│ 1. System Prompt    │  Embedded scientific best practices
│    Principles       │  (always-on, shapes LLM behavior)
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 2. Tool Priority    │  Load real data before analysis
│    Hierarchy        │  (enforced by tool ordering)
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 3. Code Scanner     │  Regex patterns block synthetic data
│                     │  generation, result fabrication
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 4. Data Validator   │  Checks for NaN, Inf, zero variance,
│                     │  suspicious smoothness
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 5. Bounds Checker   │  Domain-specific value range warnings
└────────┬────────────┘
         ▼
    Code executes
```

All layers are configurable and extensible via `AgentConfig`.

---

## Wizard Architecture

The self-assembly wizard is a separate module (`sciagent_wizard`) that orchestrates agent generation:

```
User describes domain
        │
        ▼
┌─────────────────────┐
│ Package Discovery   │  PyPI, bio.tools, Papers With Code, PubMed
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ Doc Fetcher         │  PyPI, GitHub, ReadTheDocs, homepages
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ Code Generator      │  Produces one of 3 output modes:
│                     │  • Fullstack Python submodule
│                     │  • Copilot / Claude Code config files
│                     │  • Platform-agnostic Markdown specs
└────────┬────────────┘
         ▼
    Ready-to-use agent
```

---

## CLI Commands

| Command | Entry Point | Description |
|---------|-------------|-------------|
| `sciagent` | `sciagent.cli:app` | Main CLI — launch your agent |
| `sciagent-web` | `sciagent.web.app:main` | Web UI server |
| `sciagent wizard` | `sciagent_wizard:main` | Self-assembly wizard |
| `sciagent-public` | `sciagent_wizard:main_public` | Public wizard with GitHub OAuth |
| `sciagent-docs` | `sciagent_wizard.docs_ingestor:main` | Documentation ingestor |

---

## Directory Structure

```
sciagent/
├── src/sciagent/               # Core framework
│   ├── base_agent.py           # BaseScientificAgent
│   ├── config.py               # AgentConfig
│   ├── cli.py                  # Terminal REPL
│   ├── agents/                 # Default agent presets + converter
│   ├── data/                   # Data resolver & caching
│   ├── guardrails/             # Scanner, validator, bounds
│   ├── mcp/                    # MCP server
│   ├── prompts/                # System prompt fragments
│   ├── tools/                  # Sandbox, fitting, registry
│   └── web/                    # Quart web UI
├── src/sciagent_wizard/        # Self-assembly wizard
│   ├── generators/             # Code generators for each output mode
│   ├── sources/                # Package discovery (PyPI, bio.tools, etc.)
│   ├── docs_ingestor/          # Documentation fetcher
│   └── prompts/                # Wizard conversation prompts
├── templates/                  # Blank templates & default agents/skills
├── examples/                   # Worked examples (csv_analyst)
└── tests/                      # Test suite
```

---

## Further Reading

- [API / Programmatic Usage](api-usage.md) — build agents in code
- [Copilot Agents & Skills Reference](copilot-agents.md) — agent/skill file format details
- [Installation](installation.md) — setup instructions
