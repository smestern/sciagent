# Using SciAgent Agents and Skills in VS Code & Claude Code

> **New here?** Start with [Getting Started: Copilot / Claude Code](getting-started-copilot.md) for a step-by-step setup walkthrough. This page is the detailed reference.

This guide explains how to use sciagent's default agents and skills — and
your own custom ones — as **VS Code GitHub Copilot custom agents**,
**Agent Skills**, and **Claude Code sub-agents**.

> **VS Code docs reference:**
> [Custom agents in VS Code](https://code.visualstudio.com/docs/copilot/customization/custom-agents)
> · [Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

---

## What are VS Code custom agents?

Custom agents are Markdown files (`.agent.md`) with YAML frontmatter
that configure Copilot Chat with specialized instructions, tools, and
handoff workflows.  When you select an agent from the **Agents dropdown**
in Copilot Chat, its instructions and tools are applied to the
conversation.

VS Code also detects `.md` files in `.claude/agents/`, following the
[Claude Code sub-agents format](https://code.claude.com/docs/en/sub-agents).
This means you can use the same agent definitions across VS Code Copilot
and Claude Code.

## What are Agent Skills?

Agent Skills are folders containing a `SKILL.md` file that teach Copilot
specialized capabilities — instructions, checklists, and procedures it
can load on-demand.  Skills follow the open
[Agent Skills](https://agentskills.io/) standard and work across VS Code
Copilot, Copilot CLI, and the Copilot coding agent.

**Skills vs Agents** — when to use which:

| | Agents | Skills |
|---|--------|--------|
| **What they are** | Personas with tools, handoffs, and constraints | Procedural capabilities loaded on-demand |
| **How they activate** | Select from the Agents dropdown | Auto-loaded by relevance or invoked via `/slash` |
| **Handoff workflows** | Yes — buttons connect agents in sequence | No — skills add knowledge, not workflow routing |
| **Tool restrictions** | Can restrict which tools are available | No tool restrictions — uses the active tool set |
| **Best for** | Multi-step workflows with distinct roles | Adding domain expertise or review checklists |

You can use **agents only**, **skills only**, or **both together**.  When
both are active, the skill's instructions augment the agent's persona.

---

## Quick Start: Using the Default Agents

SciAgent ships 5 default agents in the [`templates/agents/`](../templates/agents/) directory.
To use them:

### VS Code Copilot

```bash
# Copy the .github/ folder into your workspace root
cp -r templates/agents/.github/  /path/to/your/workspace/
```

Or install instruction templates with the transition script:

```bash
python scripts/install_templates.py --layout hybrid --target workspace
```

Open VS Code → Copilot Chat → click the **Agents dropdown** → select an
agent (e.g. "rigor-reviewer").

### Claude Code

```bash
# Copy the .claude/ folder into your workspace root
cp -r templates/agents/.claude/  /path/to/your/workspace/
```

Run Claude Code — it auto-detects agents in `.claude/agents/`.

### Both at once

```bash
cp -r templates/agents/.github/ templates/agents/.claude/ /path/to/your/workspace/
```

---

## Quick Start: Using the Default Skills

SciAgent ships 6 default skills in the [`templates/skills/`](../templates/skills/) directory.
To use them:

```bash
# Copy the skill directories into your workspace's .github/skills/
mkdir -p /path/to/your/workspace/.github/skills
cp -r templates/skills/*  /path/to/your/workspace/.github/skills/
```

In VS Code → Copilot Chat → type `/` to see available skills as slash
commands (e.g. `/rigor-reviewer`, `/data-qc`).

> **Note:** The `scientific-rigor` skill has `user-invokable: false` — it
> auto-loads whenever Copilot detects scientific analysis, without
> appearing in the `/` menu.

### Using Both Agents and Skills

```bash
# Copy agents AND skills into your workspace
cp -r templates/agents/.github/ templates/agents/.claude/ /path/to/your/workspace/
mkdir -p /path/to/your/workspace/.github/skills
cp -r templates/skills/*  /path/to/your/workspace/.github/skills/
```

When both are installed, you get agent **workflow handoffs** (planner →
QC → analysis → rigor review → report) *and* skill **slash commands**
for ad-hoc use.  The `scientific-rigor` skill auto-loads to supplement
any active agent with rigor principles.

---

## Default Agent Roster

| Agent | Role | Tools | Mode |
|-------|------|-------|------|
| **analysis-planner** | Design analysis roadmap | codebase, search, fetch | Read-only |
| **data-qc** | Check data quality | codebase, terminal, editFiles, search | Full |
| **rigor-reviewer** | Audit rigor of results | codebase, search, fetch | Read-only |
| **report-writer** | Generate structured reports | codebase, editFiles, search, fetch | Write |
| **code-reviewer** | Review scripts | codebase, search | Read-only |

### Handoff Workflow

The agents are wired together with **handoff buttons** — suggested next
actions that appear after a chat response completes:

```
┌──────────────────┐     ┌──────────┐     ┌─────────────────────┐
│ Analysis Planner │ ──► │ Data QC  │ ──► │ Your Domain Agent   │
└──────────────────┘     └──────────┘     └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Rigor Reviewer     │
                                          └─────────┬───────────┘
                                                    │
                                          ┌─────────▼───────────┐
                                          │  Report Writer      │
                                          └─────────────────────┘

         Code Reviewer ◄── invoke standalone on any script
```

- **Planner** → hands off to **Data QC** ("Run quality checks")
- **Data QC** → hands off to your domain agent ("Proceed to analysis")
- Your agent → hands off to **Rigor Reviewer** ("Review results")
- **Rigor Reviewer** → hands off to **Report Writer** ("Generate report")
- **Code Reviewer** is standalone — invoke it on any script

Handoff buttons appear at the bottom of the chat response.  Clicking one
switches to the target agent with the prompt pre-filled.

---

## Default Skill Roster

| Skill | Slash Command | Description | Auto-loads? |
|-------|---------------|-------------|-------------|
| **scientific-rigor** | *(hidden)* | Mandatory rigor principles: data integrity, objectivity, sanity checks, uncertainty, reproducibility | Yes — always |
| **analysis-planner** | `/analysis-planner` | Step-by-step analysis planning methodology with incremental validation | No |
| **data-qc** | `/data-qc` | Systematic 6-point data quality checklist with severity-rated reporting | No |
| **rigor-reviewer** | `/rigor-reviewer` | 8-point scientific rigor audit checklist | No |
| **report-writer** | `/report-writer` | Publication-quality report generation template and guidelines | No |
| **code-reviewer** | `/code-reviewer` | 7-point code review checklist for scientific scripts | No |

### How Skills Load

Skills use **progressive disclosure** — Copilot only loads what's needed:

1. **Discovery** — Copilot reads `name` and `description` from each
   `SKILL.md` frontmatter (always available, lightweight).
2. **Instructions** — When your request matches a skill's description,
   Copilot loads the full `SKILL.md` body into context.
3. **Resources** — Additional files in the skill directory (scripts,
   examples) load only when referenced.

The `scientific-rigor` skill is special: it has `user-invokable: false`
so it never appears in the `/` menu, but Copilot auto-loads it whenever
scientific data analysis is relevant.

---

## Customizing Agents for Your Domain

Each agent file has a `## Domain Customization` section at the bottom
with placeholder comments.  Add your domain-specific knowledge there:

```markdown
## Domain Customization

<!-- Add domain-specific review criteria below this line. -->

### Electrophysiology-Specific Checks
- Membrane potential should be between -90 and +60 mV
- Series resistance must be < 20 MΩ
- Always verify liquid junction potential correction
- Check for 60 Hz line noise artifacts
```

### Adding shared instructions

Create a `.github/instructions/my-domain.instructions.md` file with
domain knowledge that applies to all agents.  Reference it from any
agent's body via a Markdown link:

```markdown
Follow the [domain instructions](.github/instructions/my-domain.instructions.md).
```

VS Code will load the referenced file as additional context.

---

## Creating Agents from Your AgentConfig

If you have an existing `AgentConfig` in Python, convert it to
`.agent.md` / `.claude` files with the converter script:

```bash
python scripts/convert_to_agents.py \
    --from-config examples.csv_analyst.config:CSV_CONFIG \
    -o ./my_project
```

This produces:

```
my_project/
    .github/
        agents/csv-analyst.agent.md
        instructions/csv-analyst.instructions.md
    .claude/
        agents/csv-analyst.md
```

With `--skills`:

```
my_project/
    .github/
        agents/csv-analyst.agent.md
        instructions/csv-analyst.instructions.md
        skills/csv-analyst/SKILL.md
    .claude/
        agents/csv-analyst.md
```

### Options

```
--format vscode|claude|both    Which format(s) to generate (default: both)
--include-defaults             Also copy the 5 default agents (+ 6 skills with --skills)
--skills                       Also generate SKILL.md files
```

### Programmatic usage

```python
from sciagent.config import AgentConfig
from sciagent.agents.converter import agent_to_copilot_files

config = AgentConfig(
    name="my-agent",
    display_name="My Agent",
    description="Analyzes my data",
    instructions="You are an expert in ...",
)

# Generate agents only
agent_to_copilot_files(config, output_dir="./my_project")

# Generate agents AND a matching skill
agent_to_copilot_files(config, output_dir="./my_project", skills=True)
```

To also copy the 6 default skills:

```python
from sciagent.agents.converter import copy_default_skills

copy_default_skills("./my_project")
```

---

## Creating Agents from YAML

For users who prefer not to write Python, the converter also accepts a
YAML config file:

```bash
python scripts/convert_to_agents.py \
    --from-yaml my_agent.yaml \
    -o ./my_project
```

See [`templates/agent_config.example.yaml`](../templates/agent_config.example.yaml)
for the full schema.

### Minimal YAML example

```yaml
name: my-domain-agent
display_name: My Domain Agent
description: Analyzes domain-specific scientific data
instructions: |
  You are an expert in [your domain].
  ## Key Knowledge
  - Concept 1
  - Concept 2
model: claude-sonnet-4.5
rigor_level: standard
```

---

## Using the Wizard

The self-assembly wizard already generates Copilot/Claude agent files as
one of its output modes:

```bash
sciagent wizard -m copilot_agent
```

The wizard interviews you about your research domain, discovers relevant
packages, fetches their documentation, and generates a complete agent
project with `.agent.md`, `.claude`, instructions, and docs.  This is
the most comprehensive way to create a domain-specific agent.

---

## Claude Code Compatibility

VS Code detects **both** formats:

| Location | Format | Detected by |
|----------|--------|-------------|
| `.github/agents/*.agent.md` | VS Code YAML frontmatter | VS Code Copilot |
| `.claude/agents/*.md` | Claude YAML frontmatter | VS Code + Claude Code |

VS Code automatically maps Claude-specific tool names to VS Code
equivalents:

| Claude tool | VS Code equivalent |
|-------------|-------------------|
| `Read` | `codebase` |
| `Write` | `editFiles` |
| `Edit` | `editFiles` |
| `Bash` | `terminal` |
| `Grep` | `search` |
| `Glob` | `codebase` |

If you only want to maintain one set of files, the `.claude/agents/`
format works in both environments.

---

## Sharing Agents Across Teams

### Workspace-level (recommended)

Commit the `.github/agents/` and/or `.claude/agents/` directories to
your Git repository.  Everyone who clones the repo gets the agents
automatically.

### Organization-level

GitHub supports defining agents at the organization level.  Enable
discovery with:

```json
"github.copilot.chat.organizationCustomAgents.enabled": true
```

See [GitHub docs on organization agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents).

### Custom locations

Configure VS Code to search additional directories for agent files:

```json
"chat.agentFilesLocations": [
    { "directory": "/path/to/shared/agents" }
]
```

---

## Agent File Format Reference

### VS Code `.agent.md`

```yaml
---
description: One-line description shown as placeholder text
name: agent-slug
tools:
  - codebase
  - terminal
  - search
  - fetch
  - editFiles
handoffs:
  - label: "Next Step"
    agent: target-agent
    prompt: "Context for the next agent."
    send: false
---

Agent instructions go here in Markdown.
```

### Claude `.md`

```yaml
---
name: agent-slug
description: One-line description
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

Agent instructions go here in Markdown.
```

### Key fields

| Field | Description |
|-------|-------------|
| `name` | Agent slug — appears in the dropdown |
| `description` | Placeholder text in the chat input |
| `tools` | Available tools (VS Code: YAML list; Claude: comma-separated) |
| `handoffs` | Suggested next actions after response |
| `model` | AI model to use (optional) |
| `user-invokable` | Show in dropdown (default: true) |

### Skill `SKILL.md`

```yaml
---
name: skill-name
description: What the skill does and when to use it (max 1024 chars)
argument-hint: Hint text shown in the chat input when invoked
user-invokable: true        # false to hide from /menu (auto-load only)
disable-model-invocation: false  # true to require manual /slash invocation
---

Skill instructions go here in Markdown.
```

### Skill key fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Lowercase slug, must match directory name (max 64 chars) |
| `description` | Yes | Capabilities and use cases for skill discovery (max 1024 chars) |
| `argument-hint` | No | Hint shown when invoked as `/slash` command |
| `user-invokable` | No | Show in `/` menu (default: `true`) |
| `disable-model-invocation` | No | Prevent auto-loading (default: `false`) |

---

## Troubleshooting

**Agents don't appear in VS Code:**
- Ensure files are in `.github/agents/` (not just `agents/`)
- Check VS Code version is 1.106+ (agents require this)
- Run `Ctrl+Shift+P` → "Chat: Diagnostics" to see loaded agents

**Skills don't appear in the `/` menu:**
- Ensure each skill is in its own directory: `.github/skills/<name>/SKILL.md`
- The directory name must match the `name` field in the YAML frontmatter
- Skills with `user-invokable: false` (like `scientific-rigor`) are
  intentionally hidden — they auto-load when relevant
- Type `/skills` in chat to open the Configure Skills menu

**Handoff buttons don't appear:**
- Verify the target agent name matches exactly
- Check the `handoffs` YAML syntax

**Claude Code doesn't detect agents:**
- Ensure files are in `.claude/agents/` at the workspace root
- File extension must be `.md`
