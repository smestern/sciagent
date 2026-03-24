# Getting Started: VS Code Plugin

The fastest way to use SciAgent. The prebuilt plugin ships **6 agents** and **7 skills** — no Python install required.

> **Want custom domain agents instead?** See [Getting Started: Wizard](getting-started-copilot.md) to generate agents tailored to your research field.

---

## Overview

The SciAgent plugin adds a team of scientific analysis agents directly into VS Code Copilot Chat. Each agent has a specialized role (planning, coding, reviewing, reporting) and they hand off to each other in a pipeline that enforces scientific rigor at every step.

This mode is ideal when you want:
- Zero-config scientific rigor in VS Code
- Multi-agent workflows with automatic handoffs
- Domain customization via the `/configure-domain` skill
- No Python runtime or package installation

---

## Step 1: Get the Plugin

### Option A: From a GitHub Release

Download the latest release from [GitHub Releases](https://github.com/smestern/sciagent/releases). The plugin is in the `dist/sciagent/` directory.

### Option B: Clone and Build Locally

```bash
git clone https://github.com/smestern/sciagent.git
cd sciagent
pip install -e ".[all]"
python scripts/build_plugin.py -o build/plugin/sciagent
```

The built plugin is at `build/plugin/sciagent/`.

---

## Step 2: Add the Plugin to VS Code

Open VS Code Settings (JSON) (`Ctrl+Shift+P` → "Preferences: Open User Settings (JSON)") and add:

```jsonc
// settings.json
"chat.plugins.paths": {
    // Use the path where you downloaded or built the plugin:
    "/path/to/sciagent/dist/sciagent/.github/plugin": true
    // Or for local builds:
    // "/path/to/sciagent/build/plugin/sciagent/.github/plugin": true
}
```

---

## Step 3: Restart VS Code

Reload the window (`Ctrl+Shift+P` → "Reload Window") or restart VS Code entirely.

Open **Copilot Chat** and you should see the SciAgent agents in the **Agents dropdown**.

---

## Step 4: Start Using Agents

Type `@sci-coordinator` in Copilot Chat to get started. The coordinator routes your request to the right specialist agent.

### Agents

| Agent | Role | What it does |
|-------|------|-------------|
| `@sci-coordinator` | Entry point | Routes tasks to the right specialist agent |
| `@sci-coder` | Coding | Writes analysis code with built-in rigor enforcement |
| `@sci-reviewer` | Review | Audits code and results for correctness, reproducibility, and scientific rigor |
| `@sci-report-writer` | Reporting | Generates publication-quality reports with uncertainty quantification |
| `@sci-docs-ingestor` | Documentation | Ingests Python library docs into structured API references |
| `@sci-domain-assembler` | Configuration | Configures SciAgent for your specific research domain |

### Skills

Skills are slash-command capabilities that any agent can use:

| Skill | Command | Description |
|-------|---------|-------------|
| Analysis Planner | `/analysis-planner` | Design step-by-step analysis pipelines |
| Configure Domain | `/configure-domain` | First-time domain setup (interview + package discovery) |
| Data QC | `/data-qc` | Systematic data quality control checks |
| Docs Ingestor | `/docs-ingestor` | Learn an unfamiliar Python library |
| Report Writer | `/report-writer` | Generate structured scientific reports |
| Review | `/review` | Code + scientific rigor audit |
| Scientific Rigor | *(auto-loads)* | Always-on rigor principles (data integrity, objectivity, reproducibility) |

### Typical Workflow

```
You: @sci-coordinator I have calcium imaging data in traces.csv.
     Find responsive neurons and characterize their response profiles.

Coordinator → Analysis Planner → Data QC → Coder → Rigor Reviewer → Report Writer
```

Each agent hands off to the next with suggested actions. The final output is a structured report with figures, statistics, and reproducibility metadata.

---

## Step 5: Customize for Your Domain

The plugin works out of the box for general scientific analysis. To specialize it for your research field, use the `/configure-domain` skill:

```
You: /configure-domain

Agent: What is your research domain?
You: Patch-clamp electrophysiology — I record from neurons using pyABF files...
```

The skill will:
1. Interview you about your domain, data formats, and analysis workflows
2. Discover relevant Python packages (e.g., pyabf, neo, elephant, eFEL)
3. Generate domain-specific skills and documentation
4. Fill in template placeholders across your instruction files

See [Domain Examples](domains/) for pre-configured setups (intracellular-ephys, extracellular-ephys).

---

## Plugin Architecture

The plugin is built from the [`templates/`](../templates/) directory by `scripts/build_plugin.py`. The build process:

1. Reads agent definitions from `templates/agents/`
2. Inlines rigor instructions and prompt modules per agent
3. Compiles skills from `templates/skills/`
4. Generates `plugin.json` manifest
5. Outputs to `build/plugin/sciagent/` (local) or `dist/sciagent/` (CI)

```
dist/sciagent/  (or build/plugin/sciagent/)
├── README.md
├── agents/
│   ├── sci-coder.md
│   ├── sci-coordinator.md
│   ├── sci-docs-ingestor.md
│   ├── sci-domain-assembler.md
│   ├── sci-report-writer.md
│   └── sci-reviewer.md
├── skills/
│   ├── analysis-planner/
│   ├── configure-domain/
│   ├── data-qc/
│   ├── docs-ingestor/
│   ├── report-writer/
│   ├── review/
│   └── scientific-rigor/
└── .github/
    └── plugin/
        └── plugin.json
```

---

## Troubleshooting

### Agents don't appear in VS Code

- Verify the path in `settings.json` points to the `.github/plugin` directory inside the plugin folder.
- Check that `plugin.json` exists at the path you specified.
- Reload the window (`Ctrl+Shift+P` → "Reload Window").
- Make sure VS Code and Copilot Chat are up to date.

### Skills not loading

- Skills are discovered automatically from the `skills/` directory in the plugin.
- The `scientific-rigor` skill auto-loads and won't appear in the `/` menu — this is by design.

### Want to modify the agents?

The prebuilt plugin is read-only by design. If you want to customize agents:
1. **Quick edits**: Copy the plugin's `agents/` and `skills/` into your workspace's `.github/` directory and edit there.
2. **Deep customization**: Use the wizard to generate domain-specific agents — see [Getting Started: Wizard](getting-started-copilot.md).
3. **Rebuild from templates**: Edit files in `templates/` and run `python scripts/build_plugin.py -o build/plugin/sciagent --force`.

---

## Next Steps

- [Copilot Agents & Skills Reference](copilot-agents.md) — detailed file format reference, full roster, and handoff workflow
- [Getting Started: Wizard](getting-started-copilot.md) — generate custom domain agents via the self-assembly wizard
- [Domain Examples](domains/) — pre-configured domain setups
- [Showcase: PatchAgent](showcase.md) — real-world walkthrough in neurophysiology
- [Architecture](architecture.md) — how the framework fits together
