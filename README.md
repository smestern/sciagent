# 🔬 SciAgent

**A generic framework for building AI-powered scientific data analysis agents.**

SciAgent provides the infrastructure — chat UI, CLI, code sandbox, guardrails, docs, MCP server — so you can focus on your domain-specific tools and knowledge.

The idea here is to build more human-in-the-loop scientific coding tools. Landing somewhere in between the basic LLM chat interface, and the end-to-end AI for science tools. The goal of this project is not to do the science for you, but to help you write strong, rigorous, and reproducible research code. Essentially an LLM wrapper but with a few extra tools to make sure the LLM doesn't go off the rails.

**The core goal of this repo is to generate a domain-specific scientific agent in one of three output formats:**

1. **Fullstack** — a complete, runnable Python submodule with CLI and web UI
2. **Copilot / Claude Code** — config files that plug directly into VS Code Copilot or Claude Code
3. **Markdown** — platform-agnostic spec files you can paste into any LLM

**How to use this repo**

The way I envision users utilizing this repo is in one of three ways. 

1. **Markdown templates for specifying agents** - At its core, this repo contains Markdown templates to assist with building your agent. These templates are meant to be downloaded and customized for your domain specific use. The folder [/templates/](github.com/smestern/sciagent/templates/) contains templates for building and defining the agent, and prompts meant to constrain the agent to scientific rigor.
2. **Fullstack custom agent cli/web app** - This is a fullstack agent framework built on the [copilot-sdk](https://github.com/github/copilot-sdk). Essentially this aims to use your custom domain tools in three ways: 
   1. Direct tool use by the Agent so it can do things like, direct inspect data, get metadata and plan work
   2. A custom code execution environment with preloaded packages and tools.
   3. Producing reproducible scripts for reuse with other data.
3. **A self-assembling wizard** - ***VERY WIP*** Built for novice coders. Describe your research domain to the self-assembly wizard and it discovers relevant packages, fetches their documentation, and generates a ready-to-use agent in your chosen format.

Ideally, I was hoping to host a public version of the wizard for open use - however, I can't afford the hosting / llm api fees as a grad student. If you are a company that would be willing to help out, please contact me.

Check out [PatchAgent](https://github.com/smestern/patchAgent) for a real-world example in neurophysiology.

Built on the [GitHub Copilot SDK](https://github.com/features/copilot).

---

## Quick Start

```bash
pip install sciagent[all]       # install everything
sciagent wizard                 # launch the self-assembly wizard
```

The wizard walks you through a conversation — describe your research domain, confirm discovered packages, and choose an output mode. A ready-to-use agent drops out the other end.

---

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

---

## Build Your Own Agent

The primary way to create an agent is the **self-assembly wizard**. It discovers domain-specific packages from PyPI, bio.tools, Papers With Code, and PubMed — then generates a complete agent in one of three output modes.

```bash
sciagent wizard                       # web UI (default)
sciagent wizard --cli                 # terminal REPL
sciagent wizard -m fullstack          # choose output mode up front
sciagent wizard -m copilot_agent
sciagent wizard -m markdown
```

You can also pick the output mode during the wizard conversation itself.

### Mode 1 — Fullstack (`fullstack`)

Generates a complete, runnable Python submodule you can install and launch immediately:

```
my_agent/
    __init__.py
    __main__.py
    agent.py           # BaseScientificAgent subclass
    config.py           # AgentConfig with bounds, patterns, chips
    tools.py            # Domain tool functions
    domain_prompt.py    # System prompt expertise section
    requirements.txt
    docs/               # Auto-fetched package documentation
    README.md
```

```bash
cd my_agent && pip install -r requirements.txt
python -m my_agent          # CLI
python -m my_agent --web    # Web UI
```

### Mode 2 — Copilot / Claude Code (`copilot_agent`)

Generates config files for **VS Code GitHub Copilot** custom agents and **Claude Code** sub-agents — no Python runtime needed:

```
my_agent/
    .github/
        agents/my-agent.agent.md              # VS Code custom agent
        instructions/my-agent.instructions.md
    .claude/
        agents/my-agent.md                    # Claude Code sub-agent
    docs/               # Auto-fetched package documentation
    README.md
```

Copy the project into your workspace and the agents appear automatically in VS Code Copilot chat or Claude Code.

### Mode 3 — Platform-Agnostic Markdown (`markdown`)

Generates a self-contained set of Markdown files that define the agent's persona, tools, data handling, guardrails, and workflow. Paste them into **any** LLM — ChatGPT, Gemini, Claude, local models, etc.:

```
my_agent/
    agent-spec.md       # Master spec linking everything
    system-prompt.md    # Copy-paste into any LLM
    tools-reference.md  # Available packages & APIs
    data-guide.md       # Supported formats, structure, ranges
    guardrails.md       # Bounds, forbidden patterns, safety
    workflow.md         # Step-by-step analysis workflow
    docs/               # Auto-fetched package documentation
    README.md
```

### Automatic Package Documentation

All three modes automatically fetch documentation for discovered domain packages from PyPI, GitHub, ReadTheDocs, and package homepages. The docs are written to a `docs/` directory and referenced in the agent's system prompt so it knows how to use each library.

### Documentation Templates

All three modes also generate a suite of **documentation templates** in `docs/`, generalized from [PatchAgent](https://github.com/smestern/patchAgent)'s hand-crafted documentation. These templates define the structure for comprehensive agent documentation:

| Template | Purpose |
|----------|---------|
| `agents.md` | Sub-agent roster — roles, capabilities, trigger phrases |
| `operations.md` | Standard operating procedures — rigor policy, workflows, parameters, reporting |
| `skills.md` | Skill overview — purpose, capabilities, trigger keywords |
| `tools.md` | Tool API reference — signatures, parameters, return schemas |
| `library_api.md` | Primary domain library reference — classes, pitfalls, recipes |
| `workflows.md` | Standard analysis workflows — step-by-step procedures |

The wizard auto-fills these templates from your conversation. You can also **use them manually** — find the blank templates at `src/sciagent/wizard/generator/templates/`, copy them into your project, and fill in the `<!-- REPLACE: ... -->` placeholder comments by hand. Each placeholder includes a description and example.

---

## Programmatic Usage

If you prefer to wire things up in code rather than using the wizard, you can build an agent manually in a few steps.

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

## Installation

```bash
pip install sciagent            # core only
pip install sciagent[cli]       # + terminal REPL (typer, rich, prompt-toolkit)
pip install sciagent[web]       # + browser chat (quart)
pip install sciagent[wizard]    # + self-assembly wizard
pip install sciagent[all]       # everything
```

## Example: PatchAgent

[PatchAgent](https://github.com/smestern/patchAgent) is a full implementation of sciagent for electrophysiology (patch-clamp) data analysis. It demonstrates:

- Custom ABF/NWB file loaders
- Domain-specific tools (spike detection, passive properties, QC)
- Physiological bounds checking
- Specialized system prompt with neuroscience expertise

---

## Authentication (Optional)

The public wizard (`/public`) and docs ingestor (`/ingestor`) support **opt-in GitHub OAuth** via the [Copilot SDK auth flow](https://github.com/github/copilot-sdk/blob/main/docs/auth/index.md#github-signed-in-user). When enabled, users sign in with GitHub and their OAuth token is passed through to the Copilot SDK, billing LLM usage to their own Copilot subscription.

**When OAuth env vars are not set, the app behaves exactly as before — fully open, no auth.**

### Setup

1. [Create a GitHub OAuth App](https://docs.github.com/en/developers/apps/building-oauth-apps/creating-an-oauth-app):
   - **Homepage URL:** `https://your-domain.com`
   - **Authorization callback URL:** `https://your-domain.com/auth/callback`

2. Set environment variables:

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `GITHUB_OAUTH_CLIENT_ID` | Yes | OAuth App client ID |
   | `GITHUB_OAUTH_CLIENT_SECRET` | Yes | OAuth App client secret |
   | `SCIAGENT_SESSION_SECRET` | Recommended | Session cookie signing key (random string). Falls back to a key derived from the client secret. |
   | `SCIAGENT_SESSION_SECURE` | No | Set to `1` to require HTTPS for session cookies (recommended in production). |
   | `SCIAGENT_ALLOWED_ORIGINS` | No | Restrict CORS origins (default: `*`). Set to your domain in production. |

3. Run normally:

   ```bash
   sciagent-public          # public wizard with OAuth
   sciagent-docs            # docs ingestor with OAuth
   ```

### How it works

- `/auth/login` redirects to GitHub's OAuth authorize page with a CSRF `state` parameter.
- `/auth/callback` exchanges the authorization code for a `gho_*` token, validates it against the GitHub API, and stores it in an HttpOnly session cookie.
- Protected routes (`/public/`, `/ingestor/`) redirect unauthenticated users to `/auth/login`.
- The token is threaded through the agent factory to `CopilotClient({"github_token": ...})` so LLM requests run under the user's identity.

### Security notes

- No secrets are committed to the repository.
- Session cookies are `HttpOnly` and `SameSite=Lax`.
- The OAuth `state` parameter uses `secrets.token_urlsafe(32)` to prevent CSRF.
- Only `gho_*`, `ghu_*`, and `github_pat_*` tokens are accepted (classic `ghp_*` PATs are rejected).
- When OAuth is disabled (no env vars), **zero authentication code runs** — no middleware, no redirects, no session cookies.

## License

MIT
