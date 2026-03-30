# SciAgent — Workspace Instructions

## Project Overview

**SciAgent** is a framework for building domain-specific scientific analysis agents that enforce scientific rigor. It runs on the GitHub Copilot SDK and produces agents delivered primarily as VS Code plugins and Claude Code configs, with an optional fullstack Python package mode.

**SciAgent-Wizard** is the backend service that powers SciAgent's self-assembly workflow — a conversational LLM agent that interviews researchers about their domain, discovers relevant Python packages from multiple sources, and generates complete agent projects.

### Repository Roles

| Repo | Role | Package | Version |
|------|------|---------|---------|
| `sciagent` | Core framework — agents, tools, guardrails, templates, build scripts | `sciagent` | 0.5.0 |
| `sciagent-wizard` | Backend — discovery, generation, docs ingestion, web UI | `sciagent-wizard` | 0.2.0 |

Both are MIT-licensed, Python ≥3.9, alpha status.

---

## Architecture

### SciAgent Core (`sciagent/`)

```
src/sciagent/
├── base_agent.py      # BaseScientificAgent — abstract agent with guardrail middleware
├── config.py          # AgentConfig dataclass — identity, bounds, rigor level, sandbox libs
├── cli.py             # ScientificCLI — Rich terminal REPL with slash commands
├── plugins.py         # Plugin discovery via setuptools entry points
├── guardrails/        # CodeScanner (pattern-based), BoundsChecker, data validator
├── tools/             # @tool registry, code sandbox, figures, fitting, ingestion
├── web/               # Quart web UI (chat + figure streaming)
├── mcp/               # Model Context Protocol server
└── prompts/           # System prompt fragments (rigor, code execution, style)

templates/             # Source of truth for all agent/skill/instruction content
├── agents/.github/agents/   # 9 .agent.md files (coordinator → coder)
├── skills/                  # 9 SKILL.md directories
├── prompts/                 # Reusable prompt modules
└── *.md                     # operations, workflows, tools, library_api, skills

scripts/               # Build pipeline
├── build_plugin.py          # Templates → VS Code plugin (plugin.json + agents/ + skills/)
├── install_templates.py     # Templates → workspace .instructions.md files
├── convert_to_agents.py     # Legacy → .agent.md conversion
└── link_prompts.py          # Symlink prompts across packages (Windows workaround)
```

### SciAgent-Wizard (`sciagent-wizard/`)

```
src/sciagent_wizard/
├── agent.py           # WizardAgent — conversational wizard with ~13 tools
├── models.py          # WizardState, OutputMode, WizardPhase, PackageCandidate
├── analyzer.py        # File introspection → DataFileInfo (CSV, ABF, NWB, etc.)
├── rendering.py       # Template renderer (REPLACE/REPEAT placeholder substitution)
├── tools.py           # Tool handler implementations
├── auth.py            # GitHub OAuth + invite codes + session management
├── web.py             # Quart blueprint — /wizard/ routes
├── public.py          # Quart blueprint — /public/ guided mode (rate-limited)
├── generators/        # Output pipeline dispatched by OutputMode
│   ├── copilot.py          # VS Code .agent.md + .instructions.md + plugin.json (primary)
│   ├── markdown.py         # Platform-agnostic markdown spec
│   ├── fullstack.py        # Complete Python submodule with agent + config + tools
│   ├── agent_gen.py        # agent.py source generation
│   ├── config_gen.py       # config.py source generation
│   ├── prompt_gen.py       # domain_prompt.py DOMAIN_EXPERTISE constant
│   ├── tools_gen.py        # @tool wrapper per confirmed package
│   └── docs_gen.py         # Package docs → markdown files
├── sources/           # Multi-source package discovery
│   ├── pypi.py             # PyPI Simple Index + JSON API
│   ├── biotools.py         # bio.tools REST API
│   ├── papers_with_code.py # Papers with Code API
│   ├── pubmed.py           # Europe PMC / PubMed E-utilities
│   ├── google_cse.py       # Playwright headless Chromium search
│   ├── ranker.py           # Dedup + multi-source relevance boosting
│   └── domain_catalogs/    # Pre-cached JSON package lists
└── docs_ingestor/     # Deep documentation extraction
    ├── agent.py            # DocsIngestorAgent — LLM-driven section submission
    ├── crawler.py          # Multi-source doc fetcher (PyPI, GitHub, RTD)
    ├── models.py           # IngestorState, ScrapedPage, SourceType
    └── tools.py            # submit_core_classes, submit_key_functions, etc.
```

---

## Key Abstractions

### AgentConfig (`sciagent/config.py`)
Central configuration: name, display_name, description, bounds (param → min/max), forbidden_patterns, warning_patterns, rigor_level ("strict" | "standard" | "relaxed" | "bypass"), accepted_file_types, extra_libraries, model.

### BaseScientificAgent (`sciagent/base_agent.py`)
Abstract base. Subclass must implement `_load_tools()`. Features guardrail middleware that auto-scans string args >50 chars via CodeScanner. 8 retries for transient model errors.

### WizardState (`sciagent-wizard/models.py`)
Mutable accumulator across wizard phases: INTAKE → DISCOVERY → REFINEMENT → CONFIGURATION → GENERATION → COMPLETE. Tools mutate state in-place.

### Template Placeholders
```markdown
<!-- REPLACE: key — description -->
<!-- REPEAT: name --> ... <!-- END_REPEAT -->
```
Processed by `rendering.py` using context dicts built from WizardState.

---

## Build & Run Commands

### SciAgent
```bash
# Install (development)
pip install -e ".[all]"

# Build VS Code plugin from templates
python scripts/build_plugin.py -o build/plugin/sciagent [--force]

# Install templates into workspace
python scripts/install_templates.py --layout hybrid --target workspace

# Run CLI
sciagent

# Run web UI
sciagent-web

# Tests
pytest tests/ -m "not live"          # skip external API tests
pytest tests/ -m live                # external API tests only
```

### SciAgent-Wizard
```bash
# Install
pip install -e "."

# Conversational wizard
sciagent-wizard

# Guided public wizard
sciagent-wizard --public

# Docs ingestor standalone
sciagent-docs

# Docker
docker build -t sciagent-wizard .

# Dev server with hot reload
hypercorn sciagent_wizard.web:create_app --reload --bind 0.0.0.0:5000
```

---

## Conventions

### Code Style
- **Naming**: kebab-case for agent/skill slugs, PascalCase classes, snake_case functions, UPPER_CASE constants
- **Tools**: `@tool(name, description, schema)` decorator → `collect_tools(module)` for discovery
- **Async**: `asyncio.gather()` for parallel source discovery; `Semaphore(15)` caps concurrent HTTP
- **State**: Tools receive and mutate `WizardState` in-place; no return value pattern

### Template System
- All agent content lives in `templates/` — never hardcode prompt text in Python
- Build script (`build_plugin.py`) inlines rigor instructions and appends prompt modules per agent
- Agent-to-prompt mapping defined in `AGENT_PROMPT_MAP` (e.g., coder gets code_execution + reproducible_script)
- Unfilled placeholders are humanized, never cause errors

### Guardrails (always enforced)
- **CodeScanner**: regex patterns block synthetic data, result manipulation, shell escape
- **BoundsChecker**: domain-specific range validation from AgentConfig.bounds
- **RigorLevel**: STRICT → all violations block; STANDARD → CRITICAL blocks, WARNING confirms; RELAXED → warnings only
- See [sciagent-rigor.instructions.md](../.copilot/instructions/sciagent-rigor.instructions.md) for policy

### Plugin Integration
- `sciagent-wizard` registers itself via `sciagent.plugins` setuptools entry point
- `PluginRegistration` dataclass provides `register_web()`, `register_cli()`, `get_auth_token()`, `tool_providers`

---

## Output Modes (Wizard)

| Mode | Entry | Produces |
|------|-------|----------|
| `COPILOT` | `generate_copilot_via_build()` | **Primary.** Calls `build_plugin.py` via subprocess → `plugin.json` + compiled agents + skills + Claude Code agents |
| `MARKDOWN` | `generate_markdown_project()` | Platform-agnostic spec: system-prompt.md, tools-reference.md, guardrails.md |
| `FULLSTACK` | `generate_fullstack_project()` | Python package: agent.py, config.py, tools.py, domain_prompt.py, requirements.txt |

> Legacy enum values `COPILOT_AGENT` and `COPILOT_PLUGIN` are aliases for `COPILOT`.

---

## Data Flow

```
User describes domain
       ↓
   WizardAgent interview (INTAKE)
       ↓
   Multi-source discovery (PyPI, bio.tools, PubMed, Papers w/ Code, Google CSE)
       ↓
   Ranker: dedup + multi-source boost (+0.12/source)
       ↓
   User confirms packages (REFINEMENT)
       ↓
   Doc fetcher → package documentation
       ↓
   Generator dispatches on OutputMode
       ↓
   Template rendering (REPLACE/REPEAT substitution)
       ↓
   Final output: agent project ready to use
```

---

## Common Pitfalls

- **Windows symlinks**: `link_prompts.py` falls back to file copy if symlinks fail
- **Playwright dependency**: Google CSE source requires `playwright install chromium`
- **Template edits**: Change content in `templates/`, not in `build/` — build output is regenerated
- **Rigor bypass**: Only `rigor_level="bypass"` disables CodeScanner; AST/sandbox gates remain active
- **Plugin discovery**: Entry points require package to be installed (`pip install -e .`)
