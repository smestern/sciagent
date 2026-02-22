# Installation

SciAgent requires **Python 3.9+** and runs on Windows, macOS, and Linux.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.9 | `python --version` to check |
| pip | Included with Python 3.9+ |
| Git | For cloning the repo or installing from GitHub |

Optional but recommended: a virtual environment (`venv`, `conda`, etc.) to isolate dependencies.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

---

## Install from PyPI

SciAgent uses **extras** to keep the base install lightweight. Choose the variant that matches your use case:

```bash
pip install sciagent            # core only (numpy, pandas, scipy, matplotlib, copilot-sdk)
pip install sciagent[cli]       # + Rich terminal REPL (typer, prompt-toolkit, rich)
pip install sciagent[web]       # + browser chat UI (quart, quart-cors)
pip install sciagent[wizard]    # + self-assembly wizard (includes cli + web + httpx)
pip install sciagent[all]       # everything
```

> **Tip:** If you're not sure which to pick, `pip install sciagent[all]` gets you everything.

### What each extra includes

| Extra | Added packages | Use case |
|-------|---------------|----------|
| *(core)* | numpy, pandas, scipy, matplotlib, Pillow, PyYAML, github-copilot-sdk | Embedding sciagent in your own code |
| `cli` | typer, prompt-toolkit, rich | Terminal REPL with slash commands |
| `web` | quart, quart-cors | Browser-based chat UI with WebSocket streaming |
| `wizard` | cli + web + httpx, python-dotenv | Self-assembly wizard (web or CLI) |
| `all` | cli + web + wizard | Everything in one install |

---

## Install from Source (Development)

```bash
git clone https://github.com/smestern/sciagent.git
cd sciagent
pip install -e ".[all,dev]"
```

The `dev` extra adds testing and linting tools:

| Package | Purpose |
|---------|---------|
| pytest, pytest-asyncio, pytest-cov | Testing |
| black | Code formatting |
| ruff | Linting |

### Run the test suite

```bash
pytest                      # run all tests
pytest -m "not live"        # skip tests that hit external APIs
```

---

## Verify Installation

```bash
# Check the CLI is available
sciagent --help

# Check the wizard
sciagent wizard --help

# Quick smoke test — launch the wizard in CLI mode
sciagent wizard --cli
```

---

## CLI Commands

SciAgent installs several command-line entry points:

| Command | Description |
|---------|-------------|
| `sciagent` | Main CLI — launch your agent in terminal REPL mode |
| `sciagent-web` | Launch your agent's web UI |
| `sciagent wizard` | Start the self-assembly wizard |
| `sciagent-public` | Public-facing wizard with optional GitHub OAuth |
| `sciagent-docs` | Documentation ingestor with optional GitHub OAuth |

---

## Next Steps

- **New to sciagent?** Pick your output stream:
  - [Getting Started: Fullstack](getting-started-fullstack.md) — a runnable Python agent with CLI & web UI
  - [Getting Started: Copilot / Claude Code](getting-started-copilot.md) — VS Code & Claude Code config files
  - [Getting Started: Markdown](getting-started-markdown.md) — platform-agnostic spec files for any LLM
- **Want to code it by hand?** See [API / Programmatic Usage](api-usage.md)
- **Curious about the internals?** See [Architecture](architecture.md)
