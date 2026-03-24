# Getting Started: Fullstack Agent

This guide walks you through creating a **complete, runnable Python agent** with CLI and web UI using the self-assembly wizard.

> **Prerequisites:** Python 3.9+ installed. See [Installation](installation.md) if you haven't installed sciagent yet.

---

## Overview

The **Fullstack** output mode generates a self-contained Python submodule that you can install, launch, and customize immediately. It includes:

- A `BaseScientificAgent` subclass with your domain tools
- `AgentConfig` with branding, bounds, and suggestion chips
- Pre-built CLI (Rich terminal REPL) and web UI (Quart WebSocket chat)
- Sandboxed code execution with guardrails
- Auto-fetched documentation for discovered packages

---

## Step 1: Install SciAgent

```bash
pip install sciagent[all]
```

This installs the core framework, CLI, web UI, and wizard.

---

## Step 2: Run the Wizard

```bash
sciagent wizard -m fullstack
```

Or launch the wizard without specifying a mode and choose **Fullstack** during the conversation:

```bash
sciagent wizard                # web UI (default)
sciagent wizard --cli          # terminal REPL
```

### What the wizard does

1. **Asks about your research domain** — describe what you study, what data formats you use, and what analyses you need.
2. **Discovers packages** — searches PyPI, bio.tools, Papers With Code, and PubMed for relevant libraries.
3. **Confirms the package list** — you approve, remove, or add packages.
4. **Fetches documentation** — downloads docs from PyPI, GitHub, ReadTheDocs, and package homepages.
5. **Generates your agent** — outputs a complete Python submodule.

---

## Step 3: Explore the Generated Agent

The wizard creates a directory like this:

```
my_agent/
├── __init__.py
├── __main__.py           # Entry point — CLI or web
├── agent.py              # BaseScientificAgent subclass with your domain tools
├── config.py             # AgentConfig — branding, bounds, patterns, chips
├── tools.py              # Domain-specific tool functions
├── domain_prompt.py      # System prompt expertise section
├── requirements.txt      # Python dependencies
├── docs/                 # Auto-fetched package documentation
│   ├── numpy.md
│   ├── scipy.md
│   └── ...
└── README.md
```

### Key files

| File | What to customize |
|------|-------------------|
| `config.py` | Agent name, description, accepted file types, suggestion chips, domain bounds |
| `agent.py` | Add or modify tools, change tool loading logic |
| `tools.py` | Domain-specific tool implementations (data loaders, analyzers, etc.) |
| `domain_prompt.py` | Expertise paragraph injected into the system prompt |
| `requirements.txt` | Add any extra Python packages your tools need |

---

## Step 4: Install & Launch

```bash
cd my_agent
pip install -r requirements.txt

# Terminal REPL
python -m my_agent

# Web UI
python -m my_agent --web
```

The **CLI** gives you a Rich-powered terminal with:
- Markdown rendering of agent responses
- Slash commands (`/help`, `/clear`, `/export`, etc.)
- File upload via drag-and-drop or path arguments
- Command history

The **Web UI** gives you a browser-based chat with:
- WebSocket streaming
- Dark / light theme
- File upload
- Inline figure rendering

---

## Step 5: Customize Your Agent

### Adding a new tool

Edit `agent.py` and add a tool in `_load_tools()`:

```python
def _load_tools(self):
    tools = self._base_tools()  # sandbox, fitting, etc.
    tools.append(self._create_tool(
        "my_custom_tool",
        "Description of what this tool does",
        {"param": {"type": "string", "description": "Input parameter"}},
        self._my_custom_tool,
    ))
    return tools

async def _my_custom_tool(self, param: str) -> str:
    # Your implementation here
    return f"Result: {param}"
```

### Adjusting bounds

Edit `config.py` to add domain-specific value range checks:

```python
config = AgentConfig(
    ...
    bounds={
        "temperature": (0, 1000),      # Kelvin
        "pressure": (0, 1e6),          # Pascals
        "concentration": (0, 100),     # mM
    },
)
```

The bounds checker will warn the agent (and user) when computed values fall outside these ranges.

### Modifying the system prompt

Edit `domain_prompt.py` to change the expertise injected into the agent's system prompt. This shapes the agent's "personality" and domain knowledge.

### Adding forbidden code patterns

Edit `config.py` to add regex patterns that the code scanner should block:

```python
config = AgentConfig(
    ...
    forbidden_patterns=[
        r"np\.random\.(rand|randn|seed)\b",       # Block synthetic data generation
        r"sklearn\.datasets\.make_",               # Block fake datasets
    ],
)
```

---

## Worked Example: CSV Analyst

<!-- TODO: add examples/csv_analyst/ worked example -->
A minimal working example demonstrating `AgentConfig`, a `BaseScientificAgent` subclass
with a CSV loader tool, and CLI/web entry points is planned for a future release.

---

## Documentation Templates

The wizard also generates a suite of **documentation templates** in your agent's `docs/` directory. These help you build comprehensive documentation for your agent:

| Template | Purpose |
|----------|---------|
| `AGENTS.md` | Template-level instruction router with links |
| `builtin_agents.md` | Sub-agent roster — roles, capabilities, trigger phrases |
| `operations.md` | Standard operating procedures — rigor policy, workflows |
| `skills.md` | Skill overview — purpose, capabilities, trigger keywords |
| `tools.md` | Tool API reference — signatures, parameters, return schemas |
| `library_api.md` | Primary domain library reference — classes, pitfalls, recipes |
| `workflows.md` | Standard analysis workflows — step-by-step procedures |

Fill in the `<!-- REPLACE: ... -->` placeholder comments in each template. The wizard auto-fills what it can from your conversation.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'github_copilot_sdk'`

Install the GitHub Copilot SDK:

```bash
pip install github-copilot-sdk
```

### Web UI won't start

Make sure you installed the web extra:

```bash
pip install sciagent[web]
```

### Agent doesn't know about my domain packages

Check that the `docs/` directory contains documentation for your packages. You can manually add docs by running:

```bash
sciagent-docs    # launches the documentation ingestor
```

### Code sandbox blocks my code

The code scanner may be flagging legitimate patterns. Check `config.py` → `forbidden_patterns` and remove or adjust any overly broad rules.

---

## Next Steps

- [Getting Started: Plugin](getting-started-plugin.md) — install the prebuilt VS Code plugin (no Python needed)
- [API / Programmatic Usage](api-usage.md) — build agents without the wizard
- [Architecture](architecture.md) — how the framework fits together
- [Showcase: PatchAgent](showcase.md) — real-world example in neurophysiology
