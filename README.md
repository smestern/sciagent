# 🔬 SciAgent

**A generic framework for building AI-powered scientific data analysis agents.**

SciAgent provides the infrastructure — chat UI, CLI, code sandbox, guardrails, curve fitting, MCP server — so you can focus on your domain-specific tools and knowledge.

The Idea here is to build more human in the loop scientific coding tools. Landing somewhere in between the basic LLM chat interface, and the end-to-end AI for science tools. The goal of this project is not to do the science for you, but you help you write strong, rigorous, and reproducible research code. 
Essentially an LLM wrapper but with a few extra tools to make sure the LLM doesn't go of the rails.

This project is built to be customized. Essentially you want to load it with tools specific to your domain. Check out [patchagent](https://github.com/smestern/patchAgent) as an example


Built on the [GitHub Copilot SDK](https://github.com/features/copilot).

---

## Quick Start

```bash
pip install sciagent            # core only
pip install sciagent[cli]       # + terminal REPL (typer, rich, prompt-toolkit)
pip install sciagent[web]       # + browser chat (quart)
pip install sciagent[all]       # everything
```

## Architecture

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

## Build Your Own Agent in 4 Steps

### 1. Define your configuration

```python
from sciagent import AgentConfig, SuggestionChip

config = AgentConfig(
    name="my-agent",
    display_name="MyAgent",
    description="AI assistant for CSV data analysis",
    accepted_file_types=[".csv", ".tsv"],
    logo_emoji="📊",
    suggestion_chips=[
        SuggestionChip("Summarize data", "Summarize this dataset"),
        SuggestionChip("Plot histogram", "Plot a histogram of the first numeric column"),
    ],
    bounds={"temperature": (0, 1000), "pressure": (0, 1e6)},
)
```

### 2. Subclass BaseScientificAgent

```python
from sciagent import BaseScientificAgent

class MyAgent(BaseScientificAgent):
    def _load_tools(self):
        # Return your domain-specific tools
        tools = self._base_tools()  # sandbox, fitting, etc.
        tools.append(self._create_tool(
            "load_csv",
            "Load and preview a CSV file",
            {"file_path": {"type": "string", "description": "Path to CSV"}},
            self._load_csv,
        ))
        return tools

    async def _load_csv(self, file_path: str) -> str:
        import pandas as pd
        df = pd.read_csv(file_path)
        return f"Loaded {len(df)} rows, {len(df.columns)} columns.\n\n{df.head().to_markdown()}"
```

### 3. Run the CLI

```python
from sciagent.cli import run_cli

run_cli(lambda **kw: MyAgent(config, **kw), config)
```

### 4. Run the Web UI

```python
from sciagent.web.app import create_app

app = create_app(lambda **kw: MyAgent(config, **kw), config)
app.run(host="0.0.0.0", port=8080)
```

## What's Included

| Module | Description |
|--------|-------------|
| `sciagent.base_agent` | Abstract base class with Copilot SDK session lifecycle |
| `sciagent.config` | `AgentConfig` dataclass for all customisation |
| `sciagent.prompts` | Composable system message building blocks |
| `sciagent.guardrails` | Code scanner, data validator, bounds checker |
| `sciagent.tools` | Sandboxed code execution, curve fitting, tool registry |
| `sciagent.data` | Base data resolver with format registration & caching |
| `sciagent.cli` | Rich terminal REPL with slash commands |
| `sciagent.web` | Quart WebSocket chat UI (dark/light theme) |
| `sciagent.mcp` | MCP JSON-RPC server scaffold |

## Guardrails

SciAgent enforces scientific rigor through a 5-layer system:

1. **System prompt principles** — embedded scientific best practices
2. **Tool priority hierarchy** — load real data before analysis
3. **Code scanner** — regex patterns block synthetic data generation, result fabrication
4. **Data validator** — checks for NaN, Inf, zero variance, suspicious smoothness
5. **Bounds checker** — domain-specific value range warnings

All layers are configurable and extensible.

## Example: PatchAgent

[PatchAgent](https://github.com/smestern/patchAgent) is a full implementation of sciagent for electrophysiology (patch-clamp) data analysis. It demonstrates:

- Custom ABF/NWB file loaders
- Domain-specific tools (spike detection, passive properties, QC)
- Physiological bounds checking
- Specialized system prompt with neuroscience expertise

## License

MIT
