# Domain Configurations

SciAgent supports pre-configured research domain setups. Each domain provides tailored skills, package documentation, and analysis workflows for a specific field.

## Available Domains

| Domain | Slug | Packages | Skills |
|--------|------|----------|--------|
| [Intracellular Electrophysiology](intracellular-ephys/) | `intracellular-ephys` | pyabf, neo, elephant, eFEL | 5 |
| [Extracellular Electrophysiology](extracellular-ephys/) | `extracellular-ephys` | neo, elephant, spikeinterface, probeinterface | 5 |

## How Domains Work

A domain configuration consists of:

```
docs/domains/<slug>/
└── skills/
    ├── domain-expertise/    # Domain-specific knowledge base (terminology, methods, etc.)
    ├── <package-1>/         # Library skill (API reference, pitfalls, recipes)
    ├── <package-2>/         # Library skill
    └── ...
```

Each skill directory contains a `SKILL.md` file following the [Agent Skills](https://agentskills.io/) standard. These skills auto-load when Copilot detects relevant analysis tasks.

## Creating a New Domain

### Option A: Use the `/configure-domain` skill (recommended)

In VS Code Copilot Chat:

```
You: /configure-domain

Agent: What is your research domain?
You: I study calcium imaging in cortical slices using suite2p...
```

The skill interviews you, discovers relevant Python packages, fetches documentation, and generates a domain configuration.

### Option B: Use the wizard

```bash
sciagent wizard -m copilot
```

The wizard performs the same discovery and generation process interactively.

### Option C: Manual setup

1. Create a directory: `docs/domains/<your-slug>/skills/`
2. Add skill directories with `SKILL.md` files for each package
3. Add your domain to `manifest.yaml`

## The Manifest File

`manifest.yaml` indexes all configured domains:

```yaml
domains:
  - slug: my-domain
    name: My Research Domain
    description: What this domain covers
    packages:
      - package-1
      - package-2
    skills:
      - domain-expertise
      - package-1
      - package-2
```

## Further Reading

- [Getting Started: Plugin](../getting-started-plugin.md) — install and use the prebuilt plugin
- [Getting Started: Wizard](../getting-started-copilot.md) — generate custom domain agents
- [Copilot Agents & Skills Reference](../copilot-agents.md) — agent and skill file format details
- [Showcase: PatchAgent](../showcase.md) — real-world example of a domain-configured agent
