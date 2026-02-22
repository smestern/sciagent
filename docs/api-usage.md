# API / Programmatic Usage

If you prefer to wire things up in code rather than using the wizard, you can build an agent manually. This guide covers the `AgentConfig` dataclass, `BaseScientificAgent` subclass, tool registration, and launching via CLI or web.

> **Prerequisites:** `pip install sciagent[all]` — see [Installation](installation.md)

---

## Quick Example

A complete agent in three steps:

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

### 2. Subclass `BaseScientificAgent`

```python
from sciagent import BaseScientificAgent

class MyAgent(BaseScientificAgent):
    def _load_tools(self):
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

### 3. Run it

```python
from sciagent.cli import run_cli
from sciagent.web.app import create_app

# Terminal REPL
run_cli(lambda **kw: MyAgent(config, **kw), config)

# Or web UI
app = create_app(lambda **kw: MyAgent(config, **kw), config)
app.run(host="0.0.0.0", port=8080)
```

---

## `AgentConfig` Reference

`AgentConfig` is the central configuration dataclass. All fields:

```python
from sciagent import AgentConfig, SuggestionChip

config = AgentConfig(
    # Identity
    name="my-agent",                        # URL-safe identifier
    display_name="My Agent",                # Human-readable name
    description="What this agent does",     # Shown in UI
    logo_emoji="🔬",                        # Emoji for branding

    # Data handling
    accepted_file_types=[".csv", ".tsv", ".json"],  # File upload filter

    # UI — suggestion chips shown in the web chat
    suggestion_chips=[
        SuggestionChip("Summarize", "Summarize this dataset"),
        SuggestionChip("Plot", "Create a scatter plot of X vs Y"),
    ],

    # Guardrails — domain-specific value bounds
    bounds={
        "temperature": (0, 1000),           # (min, max)
        "pressure": (0, 1e6),
    },

    # Code scanner — regex patterns to block
    forbidden_patterns=[
        r"np\.random\.(rand|randn|seed)\b",
        r"sklearn\.datasets\.make_",
    ],
)
```

### Key fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | URL-safe agent identifier |
| `display_name` | `str` | Human-readable name |
| `description` | `str` | Agent description |
| `logo_emoji` | `str` | Branding emoji |
| `accepted_file_types` | `list[str]` | Accepted upload extensions |
| `suggestion_chips` | `list[SuggestionChip]` | Quick-action buttons in the UI |
| `bounds` | `dict[str, tuple]` | `{name: (min, max)}` for value range warnings |
| `forbidden_patterns` | `list[str]` | Regex patterns the code scanner blocks |

---

## `BaseScientificAgent` API

`BaseScientificAgent` is the abstract base class you subclass. It handles the Copilot SDK session lifecycle, system prompt assembly, and tool orchestration.

### Methods to override

| Method | Purpose |
|--------|---------|
| `_load_tools()` | Return a list of tools the agent can use |
| `_domain_prompt()` | *(optional)* Return a string appended to the system prompt |
| `_on_session_start()` | *(optional)* Hook for session initialization |

### Built-in tools from `_base_tools()`

When you call `self._base_tools()`, you get these tools automatically:

| Tool | Description |
|------|-------------|
| Code sandbox | Execute Python in a sandboxed subprocess with guardrail scanning |
| Curve fitting | Fit common models (exponential, polynomial, Gaussian, etc.) to data |
| Data resolver | Load and cache data files with format auto-detection |

### Creating custom tools

Use `self._create_tool()`:

```python
self._create_tool(
    name="tool_name",                       # Unique tool identifier
    description="What the tool does",       # Shown to the LLM
    parameters={                            # JSON Schema for arguments
        "param1": {"type": "string", "description": "..."},
        "param2": {"type": "number", "description": "...", "default": 10},
    },
    handler=self._my_handler,               # Async callable
)
```

The handler receives keyword arguments matching the parameter names:

```python
async def _my_handler(self, param1: str, param2: int = 10) -> str:
    # Do work
    return "Result as a string"
```

---

## Tool Registry

For reusable tools across multiple agents, use the tool registry:

```python
from sciagent.tools.registry import register_tool, get_tools

@register_tool(
    name="my_tool",
    description="Reusable tool",
    parameters={"x": {"type": "number"}},
)
async def my_tool(x: float) -> str:
    return str(x * 2)

# Later, in your agent:
tools = get_tools()  # Returns all registered tools
```

---

## Guardrails Configuration

### Code Scanner

The code scanner checks generated code against forbidden patterns before execution:

```python
from sciagent.guardrails.scanner import CodeScanner

scanner = CodeScanner(
    forbidden_patterns=[
        r"np\.random\.(rand|randn|seed)\b",
        r"pd\.DataFrame\(\{.*\}\)",        # Block inline DataFrame construction
    ]
)
violations = scanner.scan(code_string)
```

### Bounds Checker

The bounds checker warns when computed values fall outside expected ranges:

```python
from sciagent.guardrails.bounds import BoundsChecker

checker = BoundsChecker(bounds={"temperature": (0, 1000)})
warnings = checker.check({"temperature": 1500})
# → ["temperature=1500 outside expected range (0, 1000)"]
```

### Data Validator

The data validator checks data quality before analysis:

```python
from sciagent.guardrails.validator import DataValidator

validator = DataValidator()
issues = validator.validate(dataframe)
# Checks: NaN, Inf, zero variance, suspicious smoothness
```

---

## Data Resolver

The data resolver handles file loading with format auto-detection and caching:

```python
from sciagent.data.resolver import DataResolver

resolver = DataResolver(
    accepted_types=[".csv", ".tsv", ".json"],
    cache_dir=".cache/data",
)
data = await resolver.resolve("path/to/file.csv")
```

Register custom format handlers:

```python
@resolver.register(".abf")
async def load_abf(path: str) -> dict:
    import pyabf
    abf = pyabf.ABF(path)
    return {"sweeps": abf.sweepCount, "channels": abf.channelCount}
```

---

## MCP Server

SciAgent includes an MCP (Model Context Protocol) JSON-RPC server scaffold for exposing your agent's tools to external clients:

```python
from sciagent.mcp.server import create_mcp_server

server = create_mcp_server(agent)
server.run()  # stdio transport
```

---

## Worked Example

See [`examples/csv_analyst/`](../examples/csv_analyst/) for a minimal working agent (~50 lines) that demonstrates all the patterns above. The [csv_analyst README](../examples/csv_analyst/README.md) has full instructions.

---

## Next Steps

- [Architecture](architecture.md) — how the modules fit together
- [Getting Started: Fullstack](getting-started-fullstack.md) — wizard-generated agents
- [Showcase: PatchAgent](showcase.md) — real-world implementation in neurophysiology
