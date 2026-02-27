# <img src="logo.svg" height="32" alt="SciAgent"> SciAgent

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
   4. The agent also has the ability to ingest the docs of new packages and modify its own codebase, to give itself more power.
3. **A self-assembling wizard** - ***VERY WIP*** Built for novice coders. Describe your research domain to the self-assembly wizard and it discovers relevant packages, fetches their documentation, and generates a ready-to-use agent in your chosen format. **The wizard now lives in its own package** ([sciagent-wizard](https://github.com/smestern/sciagent-wizard)) so framework users aren't affected by wizard-only releases.

Ideally, I was hoping to host a public version of the wizard for open use - however, I can't afford the hosting / llm api fees as a grad student. If you are a company that would be willing to help out, please contact me.

Check out [PatchAgent](https://github.com/smestern/patchAgent) for a real-world example in neurophysiology.

Built on the [GitHub Copilot SDK](https://github.com/features/copilot).

## Alternate

You may be interested in [DAAF](https://github.com/DAAF-Contribution-Community/daaf), the Data Analyst Augmentation Framework, by Brian Heseung Kim! A framework with much of the same goals and ideas. We accidentally had parallel evolution of our ideas.

---

## Documentation

| # | Page | Description |
|---|------|-------------|
| 0 | **README** | This document — overview, quick start, and links |
| 1 | [Installation](docs/installation.md) | Prerequisites, install variants, CLI commands, dev setup |
| 2 | [Getting Started: Fullstack](docs/getting-started-fullstack.md) | Build a runnable Python agent with CLI & web UI |
| 3 | [Getting Started: Copilot / Claude Code](docs/getting-started-copilot.md) | Generate VS Code & Claude Code config files |
| 4 | [Getting Started: Markdown](docs/getting-started-markdown.md) | Generate platform-agnostic spec files for any LLM |
| 5 | [API / Programmatic Usage](docs/api-usage.md) | `AgentConfig`, `BaseScientificAgent`, tools, guardrails API |
| 6 | [Architecture](docs/architecture.md) | System diagram, module reference, guardrails pipeline |
| 7 | [Copilot Agents & Skills Reference](docs/copilot-agents.md) | Agent/skill file formats, roster, handoff workflow |
| 8 | [Showcase: PatchAgent](docs/showcase.md) | Real-world walkthrough in neurophysiology |

---

## Quick Start

```bash
pip install "sciagent[all] @ git+https://github.com/smestern/sciagent.git"       # install core framework + CLI + web UI
pip install "sciagent-wizard @ git+https://github.com/smestern/sciagent-wizard.git"  # install the wizard (optional)
sciagent wizard                 # launch the wizard (only available when sciagent-wizard is installed)
```

The wizard walks you through a conversation — describe your research domain, confirm discovered packages, and choose an output mode. A ready-to-use agent drops out the other end.

---

## Three Output Streams

SciAgent generates a domain-specific scientific agent in one of three formats. Pick the one that fits your workflow:

### 1. Fullstack — Python agent with CLI & web UI

A complete, runnable Python submodule you can install and launch immediately. Includes sandboxed code execution, guardrails, Rich terminal REPL, and browser-based chat UI.

```bash
sciagent wizard -m fullstack
```

**[Full setup guide →](docs/getting-started-fullstack.md)**

### 2. Copilot / Claude Code — IDE config files

Markdown-based agent definitions that plug directly into VS Code Copilot Chat or Claude Code. No Python runtime needed at the endpoint.

```bash
sciagent wizard -m copilot_agent
```

**[Full setup guide →](docs/getting-started-copilot.md)**

### 3. Markdown — platform-agnostic spec files

A self-contained set of Markdown files defining persona, tools, data handling, guardrails, and workflow. Paste into any LLM — ChatGPT, Gemini, Claude, local models, etc.

```bash
sciagent wizard -m markdown
```

**[Full setup guide →](docs/getting-started-markdown.md)**

---

## Default Scientific Agents

SciAgent ships 5 ready-to-use agents in [`templates/agents/`](templates/agents/) that implement common scientific workflow roles:

| Agent | Role |
|-------|------|
| `analysis-planner` | Design the analysis roadmap (read-only) |
| `data-qc` | Check data quality before analysis |
| `rigor-reviewer` | Audit results for scientific rigor (read-only) |
| `report-writer` | Generate structured reports |
| `code-reviewer` | Review scripts for correctness (read-only) |

These agents support handoff workflows: `planner → QC → your agent → rigor review → report`. See [Copilot Agents & Skills Reference](docs/copilot-agents.md) for details.

---

## Guardrails

SciAgent enforces scientific rigor through a 5-layer system:

1. **System prompt principles** — embedded scientific best practices
2. **Tool priority hierarchy** — load real data before analysis
3. **Code scanner** — regex patterns block synthetic data generation, result fabrication
4. **Data validator** — checks for NaN, Inf, zero variance, suspicious smoothness
5. **Bounds checker** — domain-specific value range warnings

All layers are configurable and extensible. See [Architecture](docs/architecture.md) for the full pipeline diagram.

---

## Installation

```bash
# Neither package is on PyPI yet — install from GitHub
pip install "sciagent @ git+https://github.com/smestern/sciagent.git"            # core framework only
pip install "sciagent[cli] @ git+https://github.com/smestern/sciagent.git"       # + terminal REPL (Rich, Typer)
pip install "sciagent[web] @ git+https://github.com/smestern/sciagent.git"       # + browser chat UI (Quart)
pip install "sciagent[all] @ git+https://github.com/smestern/sciagent.git"       # core + CLI + web

# Self-assembly wizard (separate package)
pip install "sciagent-wizard @ git+https://github.com/smestern/sciagent-wizard.git"
```

The wizard is a **separate package** (`sciagent-wizard`) that registers itself as a plugin via the `sciagent.plugins` entry-point group. Installing it automatically adds the `sciagent wizard` CLI command, web blueprints (`/wizard/`, `/public/`, `/ingestor/`), and the `ingest_library_docs` tool — no configuration needed.

See [Installation](docs/installation.md) for prerequisites, dev setup, and verification steps.

---

## Plugin Architecture

SciAgent uses a plugin system based on [setuptools entry points](https://packaging.python.org/en/latest/specifications/entry-points/). Any installed package can extend the framework by registering under the `sciagent.plugins` group:

```toml
# In your package's pyproject.toml
[project.entry-points."sciagent.plugins"]
my-plugin = "my_package:register_plugin"
```

The `register_plugin()` callable returns a `PluginRegistration` declaring:

| Field | Type | Purpose |
|-------|------|---------|
| `register_web` | `(app, **ctx) → None` | Register Quart blueprints and auth middleware |
| `register_cli` | `(app) → None` | Add Typer sub-commands |
| `get_auth_token` | `() → str | None` | Provide auth tokens (e.g. OAuth) |
| `supported_models` | `dict` | Declare LLM models for routing/billing |
| `tool_providers` | `dict[str, callable]` | Lazy-load tool functions |

The wizard (`sciagent-wizard`) is the first plugin built on this system. See [`src/sciagent/plugins.py`](src/sciagent/plugins.py) for the full API.

---

## See Also

- [sciagent-wizard](https://github.com/smestern/sciagent-wizard) — self-assembly wizard for building domain agents (plugin)
- [PatchAgent](https://github.com/smestern/patchAgent) — a full SciAgent implementation for electrophysiology (see [Showcase](docs/showcase.md))
- [Templates README](templates/README.md) — blank templates for manual agent specification

---

<details>
<summary><strong>Authentication (Optional)</strong></summary>

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
   | `SCIAGENT_SESSION_SECRET` | Recommended | Session cookie signing key (random string) |
   | `SCIAGENT_SESSION_SECURE` | No | Set to `1` for HTTPS-only session cookies |
   | `SCIAGENT_ALLOWED_ORIGINS` | No | Restrict CORS origins (default: `*`) |

3. Run: `sciagent-public` (wizard) or `sciagent-docs` (ingestor)

### How it works

- `/auth/login` → GitHub OAuth authorize → `/auth/callback` exchanges code for token → stored in HttpOnly session cookie
- Protected routes redirect unauthenticated users to `/auth/login`
- Token threaded through to `CopilotClient({"github_token": ...})`

### Security

- Session cookies: `HttpOnly`, `SameSite=Lax`
- CSRF protection via `secrets.token_urlsafe(32)` state parameter
- Only `gho_*`, `ghu_*`, `github_pat_*` tokens accepted (classic `ghp_*` PATs rejected)
- When OAuth is disabled: **zero auth code runs** — no middleware, no redirects, no cookies

</details>

---

## License

MIT
