# AGENTS

This is the default template-level AGENTS router for SciAgent.

Keep this file lightweight and link to detailed guidance files so agent
context stays focused and maintainable.

## Core Policy

Always follow the scientific rigor policy in
[operations.md](operations.md), especially:

- No synthetic data fabrication
- No hypothesis confirmation bias
- Mandatory sanity checks
- Transparent reporting
- Reproducibility

## Linked Guidance

- [operations.md](operations.md) — core operating principles and rigor guardrails
- [workflows.md](workflows.md) — analysis workflow selection and execution steps
- [tools.md](tools.md) — tool interface contracts and return formats
- [library_api.md](library_api.md) — domain-library API usage and pitfalls
- [skills.md](skills.md) — skill-level guidance and trigger patterns
- [builtin_agents.md](builtin_agents.md) — default scientific agent roster and handoffs

## Usage Notes

- For modular VS Code instructions, transition templates to
  `.github/instructions/*.instructions.md` using
  `python scripts/install_templates.py --layout hybrid --target workspace`.
- For a single merged file, use
  `python scripts/install_templates.py --layout mono --target workspace`.
