# Getting Started: Platform-Agnostic Markdown

This guide walks you through creating **platform-agnostic Markdown spec files** that define your agent's persona, tools, guardrails, and workflow — ready to paste into any LLM.

> **Prerequisites:** Python 3.9+ installed. See [Installation](installation.md) if you haven't installed sciagent yet.

---

## Overview

The **Markdown** output mode generates a self-contained set of Markdown files that work with **any** LLM — ChatGPT, Gemini, Claude, local models, API wrappers, or any other platform that accepts text prompts. No runtime, no SDK, no IDE integration required.

This mode is ideal when you want:
- Maximum portability across LLM platforms
- A spec you can version-control and share as plain text
- Full control over what gets pasted into each conversation
- A starting point you can hand-edit without any tooling

---

## Step 1: Install SciAgent

```bash
pip install sciagent[all]
```

---

## Step 2: Run the Wizard

```bash
sciagent wizard -m markdown
```

Or choose **Markdown** during the wizard conversation:

```bash
sciagent wizard                # web UI
sciagent wizard --cli          # terminal REPL
```

---

## Step 3: Explore the Generated Files

The wizard creates a directory like this:

```
my_agent/
├── agent-spec.md         # Master spec — links everything together
├── system-prompt.md      # Copy-paste into any LLM as the system prompt
├── tools-reference.md    # Available packages, APIs, and tool signatures
├── data-guide.md         # Supported data formats, structure, value ranges
├── guardrails.md         # Bounds, forbidden patterns, safety rules
├── workflow.md           # Step-by-step analysis workflow
├── docs/                 # Auto-fetched package documentation
│   ├── numpy.md
│   ├── scipy.md
│   └── ...
└── README.md
```

### What each file does

| File | Purpose | When to use |
|------|---------|-------------|
| `agent-spec.md` | Master document that references all other files | Read first — it's the map |
| `system-prompt.md` | The agent's persona, expertise, and behavioral rules | Paste into the LLM's system prompt or first message |
| `tools-reference.md` | Package list with usage examples and API snippets | Paste when asking the LLM to write code |
| `data-guide.md` | File formats, column schemas, expected value ranges | Paste when the LLM needs to understand your data |
| `guardrails.md` | Forbidden patterns, bounds checks, scientific rigor rules | Paste to constrain the LLM's behavior |
| `workflow.md` | Step-by-step analysis procedures | Paste to guide a multi-step analysis |
| `docs/*.md` | Detailed documentation for each discovered package | Paste selectively when the LLM struggles with a library |

---

## Step 4: Use with Your LLM

### Basic usage (any platform)

1. **Start a new conversation** with your LLM of choice.
2. **Paste `system-prompt.md`** as the system prompt (or as your first message if the platform doesn't support system prompts).
3. **Upload or paste your data file.**
4. **Ask your question** — the agent persona will guide the LLM's behavior.

### For complex analyses

Paste additional context files as needed:

```
1. Paste system-prompt.md       → sets the persona
2. Paste tools-reference.md     → tells the LLM what packages to use
3. Paste data-guide.md          → tells the LLM about your data format
4. Paste workflow.md            → gives it a step-by-step procedure
5. Upload your data             → provide the actual data
6. Ask your research question   → "Analyze the F-I curves across conditions"
```

### Platform-specific tips

| Platform | How to set the system prompt |
|----------|------------------------------|
| ChatGPT | Use "Custom Instructions" or paste as the first message |
| Claude | Use the system prompt field in the API, or paste first |
| Gemini | Paste as the first message with "You are..." framing |
| Local models (Ollama, LM Studio) | Use the `--system` flag or system prompt config |
| API calls | Use the `system` role in the messages array |

---

## Step 5: Customize the Spec Files

### Editing the system prompt

Open `system-prompt.md` and modify:

- **Expertise section** — add your domain knowledge, terminology, common pitfalls
- **Behavioral rules** — adjust tone, verbosity, and response format
- **Package preferences** — tell it which libraries to prefer or avoid

### Adding data format specifications

Edit `data-guide.md` to document:

```markdown
## Supported Formats

### CSV files
- Delimiter: comma
- Header row: first row
- Expected columns: timestamp, voltage_mV, current_pA, condition

### ABF files (Axon Binary Format)
- Open with: pyabf
- Channels: voltage (mV), current (pA)
- Typical sampling rate: 20 kHz
```

### Defining guardrails

Edit `guardrails.md` to add domain-specific safety rules:

```markdown
## Forbidden Patterns

- NEVER generate synthetic data to fill in missing values
- NEVER apply smoothing without explicit user approval
- NEVER report p-values without effect sizes

## Value Bounds

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| Temperature | 0 | 1000 | K |
| Pressure | 0 | 1e6 | Pa |
```

### Building workflows

Edit `workflow.md` to define standard analysis procedures:

```markdown
## Standard F-I Curve Analysis

1. Load ABF files from the input directory
2. Filter for current-clamp recordings (voltage units = mV)
3. Identify the stimulus period from protocol timing
4. Detect action potentials using dV/dt threshold method
5. Count spikes per sweep and compute firing rate
6. Plot frequency vs. injected current for each condition
7. Compute rheobase, max firing rate, and F-I gain
8. Run statistical comparison across conditions (ANOVA + post-hoc)
9. Generate summary table and figures
```

---

## Using the Templates Manually

You don't need the wizard to create Markdown specs. The blank templates are available at [`templates/`](../templates/):

| Template | Purpose |
|----------|---------|
| `templates/agents.md` | Sub-agent roster |
| `templates/operations.md` | Standard operating procedures |
| `templates/skills.md` | Skill overview |
| `templates/tools.md` | Tool API reference |
| `templates/library_api.md` | Library reference |
| `templates/workflows.md` | Analysis workflows |

Each template contains `<!-- REPLACE: ... -->` placeholder comments with descriptions and examples. Copy them into your project and fill in the placeholders.

The prompt fragments in [`templates/prompts/`](../templates/prompts/) can be composed into a system prompt:

| Prompt | Purpose |
|--------|---------|
| `scientific_rigor.md` | Scientific best practices |
| `code_execution.md` | Code sandbox behavior |
| `reproducible_script.md` | Script generation rules |
| `thinking_out_loud.md` | Show-your-work rules |
| `communication_style.md` | Response format guidelines |
| `incremental_execution.md` | Step-by-step execution |
| `output_dir.md` | File output conventions |

---

## Troubleshooting

### LLM ignores the guardrails

- Paste `guardrails.md` **before** your question, not after.
- Use stronger language: "You MUST follow these rules" vs. "Please try to follow."
- Some models respond better to guardrails in the system prompt vs. user messages — experiment.

### LLM doesn't know the library

- Paste the relevant `docs/*.md` file for that specific package.
- Include a code example from the library's documentation.

### Spec files are too long for context window

- Paste only the files relevant to the current task.
- Start with `system-prompt.md` + `tools-reference.md` for most tasks.
- Add `data-guide.md` and `workflow.md` only when doing structured analyses.

---

## Next Steps

- [Getting Started: Fullstack](getting-started-fullstack.md) — if you want a runnable Python agent instead
- [Getting Started: Copilot / Claude Code](getting-started-copilot.md) — if you want IDE integration
- [Templates README](../templates/README.md) — full guide to the template system
