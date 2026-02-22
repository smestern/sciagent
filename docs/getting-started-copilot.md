# Getting Started: Copilot / Claude Code Agents

This guide walks you through creating **VS Code GitHub Copilot custom agents** and **Claude Code sub-agents** using the self-assembly wizard.

> **Prerequisites:** Python 3.9+ installed. See [Installation](installation.md) if you haven't installed sciagent yet.

---

## Overview

The **Copilot / Claude Code** output mode generates config files that plug directly into VS Code Copilot Chat or Claude Code — no Python runtime needed at the endpoint. Your agents appear in the IDE's agent dropdown and can be invoked with `@agent-name`.

This mode is ideal when you want:
- Lightweight, file-based agent definitions
- IDE-native integration (no separate server)
- Handoff workflows between specialized agents
- Easy sharing with collaborators (just copy the files)

---

## Step 1: Install SciAgent

```bash
pip install sciagent[all]
```

---

## Step 2: Run the Wizard

```bash
sciagent wizard -m copilot_agent
```

Or choose **Copilot / Claude Code** during the wizard conversation:

```bash
sciagent wizard                # web UI
sciagent wizard --cli          # terminal REPL
```

---

## Step 3: Explore the Generated Files

The wizard creates a directory structure like this:

```
my_agent/
├── .github/
│   ├── agents/
│   │   └── my-agent.agent.md              # VS Code custom agent
│   └── instructions/
│       └── my-agent.instructions.md       # Detailed instructions
├── .claude/
│   └── agents/
│       └── my-agent.md                    # Claude Code sub-agent
├── docs/                                  # Auto-fetched package documentation
│   ├── numpy.md
│   ├── scipy.md
│   └── ...
└── README.md
```

### File formats

| File | Format | Used by |
|------|--------|---------|
| `.github/agents/*.agent.md` | YAML frontmatter + Markdown body | VS Code Copilot Chat |
| `.github/instructions/*.instructions.md` | Pure Markdown | Referenced by agent files |
| `.claude/agents/*.md` | Markdown with role/tools sections | Claude Code |

---

## Step 4: Add to Your Workspace

Copy the generated files into your project workspace:

```bash
# Copy VS Code agent files
cp -r my_agent/.github/agents/ .github/agents/
cp -r my_agent/.github/instructions/ .github/instructions/

# Copy Claude Code agent files
cp -r my_agent/.claude/ .claude/

# Copy the docs (referenced by agent instructions)
cp -r my_agent/docs/ docs/
```

### VS Code Copilot

1. Open your workspace in VS Code.
2. The agents appear in the **Agents dropdown** in Copilot Chat.
3. Select your agent or type `@my-agent` to invoke it.

### Claude Code

1. The `.claude/agents/` directory is automatically detected by Claude Code.
2. Invoke with `/agent my-agent` or reference in conversations.

---

## Step 5: Add the Default Scientific Agents

SciAgent ships **5 ready-to-use agents** that implement common scientific workflow roles. These are in the [`templates/agents/`](../templates/agents/) directory:

| Agent | Role | Mode |
|-------|------|------|
| `analysis-planner` | Design the analysis roadmap | Read-only |
| `data-qc` | Check data quality before analysis | Read-only |
| `rigor-reviewer` | Audit results for scientific rigor | Read-only |
| `report-writer` | Generate structured reports | Read-write |
| `code-reviewer` | Review scripts for correctness | Read-only |

### Install them

```bash
# VS Code agents
cp templates/agents/.github/agents/*.agent.md .github/agents/
cp templates/agents/.github/instructions/*.instructions.md .github/instructions/

# Claude Code agents
cp templates/agents/.claude/agents/*.md .claude/agents/
```

### Handoff workflow

The default agents are designed to work together in a pipeline:

```
analysis-planner → data-qc → your-agent → rigor-reviewer → report-writer
```

Each agent includes **handoff buttons** that suggest the next agent in the workflow. For example, after the planner designs a roadmap, it suggests handing off to `data-qc`.

---

## Step 6: Add Agent Skills

Agent Skills are folders containing a `SKILL.md` file that teach Copilot specialized capabilities. SciAgent includes 6 default skills in [`templates/skills/`](../templates/skills/):

| Skill | Purpose |
|-------|---------|
| `scientific-rigor` | Enforces scientific best practices |
| `analysis-planner` | Guides analysis design |
| `data-qc` | Data quality checks |
| `rigor-reviewer` | Results auditing |
| `report-writer` | Structured report generation |
| `code-reviewer` | Code correctness review |

```bash
# Copy skills into your workspace
cp -r templates/skills/ .github/skills/
```

Skills are loaded on-demand when the agent references them.

---

## Converting Existing Configs

You don't need the wizard to create agent files. If you already have an `AgentConfig` (Python) or YAML config, convert it directly:

### From a Python `AgentConfig`

```bash
python scripts/convert_to_agents.py --from-config my_module.config:MY_CONFIG -o .
```

This reads `MY_CONFIG` from `my_module/config.py` and generates `.agent.md` and `.claude` files.

### From a YAML file

```bash
python scripts/convert_to_agents.py --from-yaml my_agent.yaml -o .
```

See [`templates/agent_config.example.yaml`](../templates/agent_config.example.yaml) for the full annotated YAML format.

---

## Customizing Agent Files

### VS Code agent file anatomy

```markdown
---
name: my-agent
description: AI assistant for my research domain
tools:
  - command
  - file
  - web
---

# My Agent

You are a scientific research assistant specializing in...

## Instructions
@file:.github/instructions/my-agent.instructions.md

## Handoff
When the user asks for a code review, suggest: @code-reviewer
```

Key fields in the YAML frontmatter:
- `name` — agent identifier (used with `@name`)
- `description` — shown in the agent picker
- `tools` — VS Code tools the agent can use (`command`, `file`, `web`, etc.)

### Adding domain knowledge

Edit the `.instructions.md` file to add:
- Domain-specific terminology and concepts
- Preferred analysis workflows
- Package usage guidelines (reference `docs/` files)
- Data format specifications

### Adding handoff buttons

Add `## Handoff` sections to suggest related agents:

```markdown
## Handoff
When analysis is complete, suggest: @rigor-reviewer
When the user needs a report, suggest: @report-writer
```

---

## Troubleshooting

### Agent doesn't appear in VS Code

- Make sure the `.agent.md` file is in `.github/agents/` (not just `.github/`).
- Restart VS Code or reload the window (`Ctrl+Shift+P` → "Reload Window").
- Check that VS Code is up to date with Copilot Chat enabled.

### Claude Code doesn't detect agents

- Ensure files are in `.claude/agents/` with a `.md` extension.
- Check that you're using a Claude Code version that supports sub-agents.

### Skills not loading

- Skill folders must contain a `SKILL.md` file (case-sensitive).
- Ensure the skill folder is inside `.github/skills/` in your workspace.

---

## Further Reading

- [Copilot Agents & Skills Reference](copilot-agents.md) — detailed format reference, full agent/skill roster, and advanced configuration
- [Architecture](architecture.md) — how the framework fits together
- [Getting Started: Fullstack](getting-started-fullstack.md) — if you want a runnable Python agent instead
