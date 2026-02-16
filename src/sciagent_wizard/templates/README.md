# Agent Documentation Templates

This directory contains **six Markdown template files** that define the
documentation structure for a domain-specific scientific agent. They are
generalized from the [PatchAgent](https://github.com/smestern/patchAgent)
electrophysiology agent — a real-world example of a sciagent-based project.

## Two ways to use these templates

### 1. Automatic (via the wizard)

When you run `sciagent wizard`, the self-assembly wizard fills in the
placeholder comments with domain-specific content derived from your
conversation and writes the rendered files into the generated project's
`docs/` directory. No manual editing required.

### 2. Manual (copy and fill)

Copy any or all of these `.md` files into your own project and replace the
`<!-- REPLACE: ... -->` placeholder comments by hand. Each placeholder
includes a description and example so you know exactly what to put there.

## Template files

| File | Purpose |
|------|---------|
| `agents.md` | Sub-agent roster — roles, capabilities, trigger phrases |
| `operations.md` | Standard operating procedures — rigor policy, workflows, parameters, reporting |
| `skills.md` | Skill overview — purpose, capabilities, trigger keywords |
| `tools.md` | Tool API reference — signatures, parameters, return schemas |
| `library_api.md` | Primary domain library reference — classes, functions, pitfalls, recipes |
| `workflows.md` | Standard analysis workflows — step-by-step procedures for common tasks |

## Placeholder syntax

```markdown
<!-- REPLACE: placeholder_name — Description of what goes here. Example: "some example value" -->
```

- **`REPLACE`** placeholders mark a spot where a single block of content goes.
- **`REPEAT`** / **`END_REPEAT`** brackets mark a section that should be
  duplicated once per item (e.g. once per agent, skill, or tool).

Unfilled placeholders are left intact — the templates are valid Markdown at
every stage of completion.
