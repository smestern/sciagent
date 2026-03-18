# Changelog: Coordinator Routing Table Rewrite on Plugin Export

**Date:** 2026-03-15
**Scope:** `sciagent` core — build pipeline + coordinator template

---

## Summary

The coordinator agent's body contains a markdown routing table that lists all specialist agents and when to use them. Previously, this table was exported verbatim — hardcoded template names like `**analysis-planner**` appeared in the built plugin even when agents were prefixed, merged, or excluded by the build profile. This change makes the routing table dynamically rewritten during `build_plugin.py` export to match the actual built agent set.

---

## Files Changed

### `templates/agents/.github/agents/coordinator.agent.md`

**What:** Fixed the routing table entry `**sciagent-coder**` → `**coder**` to match the actual agent stem. The build prefix (e.g. `sci-`, `sciagent-`) is applied automatically during export.

**Before:**
```markdown
| Execute / implement | **sciagent-coder** | A plan or set of changes is ready to be implemented |
```

**After:**
```markdown
| Execute / implement | **coder** | A plan or set of changes is ready to be implemented |
```

### `scripts/build_plugin.py`

#### New: `_ROUTING_ROW_RE` (regex constant)

Matches markdown table rows with a bold agent name in the second column:
```
| <need> | **<agent-stem>** | <when> |
```

#### New: `_rewrite_routing_table(agent_files, profile, name_prefix)`

Post-processing function called after `_apply_body_rewrites` in `main()`. Locates the coordinator agent file among the built outputs and rewrites its routing table with three transformations:

1. **Exclude** — Rows for agents in the profile's `exclude_agents` list are removed entirely.
2. **Merge** — Rows whose agent stem was consumed by a `merge_agents` spec are renamed to the merged agent name. When two source rows map to the same merged name, they are combined into a single row:
   - "Need" descriptions joined with ` & `
   - "When" descriptions joined with `; ` (second lowercased)
3. **Prefix** — All surviving agent names receive the build's `name_prefix` via `_prefixed()`.

The function is profile-aware and no-ops gracefully when the coordinator file is absent.

#### Modified: `main()`

Added call to `_rewrite_routing_table(agent_files, profile, name_prefix)` after the existing `_apply_body_rewrites` call (~line 1308). Runs on every build regardless of profile.

---

## Build Output Examples

### Full profile with `--name-prefix sci`

All 8 agents appear prefixed:

```markdown
| Need | Agent | When to use |
|------|-------|-------------|
| Design an analysis pipeline | **sci-analysis-planner** | User has data and a research question but no plan yet |
| Check data quality | **sci-data-qc** | User has raw data that hasn't been validated |
| Review existing code | **sci-code-reviewer** | User has analysis scripts that need review |
| Audit scientific rigor | **sci-rigor-reviewer** | Analysis is complete and needs rigor validation |
| Write a report | **sci-report-writer** | Analysis and review are done, results need documentation |
| Learn a new library | **sci-docs-ingestor** | User needs to use an unfamiliar Python package |
| Set up for a domain | **sci-domain-assembler** | First-time setup or domain reconfiguration needed |
| Execute / implement | **sci-coder** | A plan or set of changes is ready to be implemented |
```

### Compact profile with `--name-prefix sci`

- `analysis-planner` and `data-qc` rows removed (excluded)
- `code-reviewer` + `rigor-reviewer` rows merged into single `**sci-reviewer**` row
- 5 rows total:

```markdown
| Need | Agent | When to use |
|------|-------|-------------|
| Review existing code & Audit scientific rigor | **sci-reviewer** | User has analysis scripts that need review; analysis is complete and needs rigor validation |
| Write a report | **sci-report-writer** | Analysis and review are done, results need documentation |
| Learn a new library | **sci-docs-ingestor** | User needs to use an unfamiliar Python package |
| Set up for a domain | **sci-domain-assembler** | First-time setup or domain reconfiguration needed |
| Execute / implement | **sci-coder** | A plan or set of changes is ready to be implemented |
```

---

## Wizard Impact Notes

The wizard generates coordinator-like content via `generators/copilot.py` and `generators/agent_gen.py`. If the wizard produces a routing table in the coordinator body, it should follow the same pattern:

- Use **bare agent stems** (e.g. `coder`, `analysis-planner`) in the template source
- Let the build pipeline apply prefixes and profile transformations
- The `_ROUTING_ROW_RE` regex expects the format: `| <text> | **<agent-name>** | <text> |`
- Merged row combination uses ` & ` for needs and `; ` for when-to-use descriptions

If the wizard directly emits final agent files (bypassing `build_plugin.py`), it should apply the same three transformations: exclude → merge → prefix.

---

## Changelog: Scientific Rigor Policy Deduplication

**Date:** 2026-03-15
**Scope:** `sciagent` core — build pipeline (`scripts/build_plugin.py`)

### Problem

The scientific rigor principles (~50 lines, 8 numbered sections) were appearing **2–3 times** in every built agent file due to two independent injection mechanisms firing on the same content:

1. **RIGOR_LINK_PATTERN replacement** — Each agent template contains `Follow the [shared scientific rigor principles](...sciagent-rigor.instructions.md).` which gets replaced with the full inline text from `sciagent-rigor.instructions.md`.
2. **AGENT_PROMPT_MAP appending** — `"scientific_rigor.md"` was listed for every agent in `AGENT_PROMPT_MAP`, causing the same 8 principles (different header casing) to be appended a second time at the end.

For **merged agents** (compact profile's `reviewer` = `code-reviewer` + `rigor-reviewer`), the inline replacement fired once per source body (×2) plus the appended module (×1) = **3 copies**.

Both source files (`sciagent-rigor.instructions.md` and `prompts/scientific_rigor.md`) contain identical content with only header styling differences.

### Changes in `scripts/build_plugin.py`

#### Modified: `AGENT_PROMPT_MAP`

Removed `"scientific_rigor.md"` from every agent's prompt list. The inline link-replacement remains as the single injection point — it places the rigor text exactly where the template author positioned the link.

**Before (every agent had it):**
```python
"coordinator": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
```

**After:**
```python
"coordinator": ["communication_style.md", "clarification.md"],
```

#### Modified: `_merge_agent_bodies()`

Added a `rigor_inlined` flag. The first source agent in a merge gets the full inline rigor text; subsequent sources get a short back-reference instead of another full copy.

**Before:**
```python
body_parts: list[str] = []
for src_name in sources:
    ...
    if rigor_text:
        replacement_block = (
            "### Shared Scientific Rigor Principles\n\n" + rigor_text
        )
        body = RIGOR_LINK_PATTERN.sub(replacement_block, body)
    body_parts.append(body.strip())
```

**After:**
```python
body_parts: list[str] = []
rigor_inlined = False
for src_name in sources:
    ...
    if rigor_text:
        if not rigor_inlined:
            replacement_block = (
                "### Shared Scientific Rigor Principles\n\n" + rigor_text
            )
            body = RIGOR_LINK_PATTERN.sub(replacement_block, body)
            rigor_inlined = True
        else:
            body = RIGOR_LINK_PATTERN.sub(
                "See *Shared Scientific Rigor Principles* above.", body,
            )
    body_parts.append(body.strip())
```

### Build Output Results

| Agent file | Before | After |
|-----------|--------|-------|
| Individual agents (coordinator, coder, etc.) | 2 copies | 1 copy |
| Merged reviewer (compact profile) | 3 copies | 1 copy + back-reference |

### Files NOT Changed

- `templates/prompts/scientific_rigor.md` — preserved; still used by `_COMPACT_SECTIONS` for the consolidated skill asset (`sciagent-templates.md`)
- `templates/agents/.github/instructions/sciagent-rigor.instructions.md` — kept as-is; remains the single source for inline rigor
- All 9 agent templates in `templates/agents/.github/agents/` — unchanged; they still contain the link that gets replaced at build time

### Wizard Impact Notes

If the wizard (`generators/copilot.py`, `generators/agent_gen.py`) emits agent files with both a rigor link **and** appended `scientific_rigor.md` content, it will produce the same duplication. To align:

- Emit the rigor link (`Follow the [shared scientific rigor principles](...).`) in the agent body **OR** append the rigor prompt module — **not both**
- If merging agents, only the first source should get the full rigor text; subsequent sources should use a back-reference
- The `prompts/scientific_rigor.md` file can still be bundled as a standalone reference document — just don't also inline it into agent bodies

---

## Changelog: Wizard Plugin Output — Platform-Agnostic Templates & Rigor Deduplication

**Scope:** `sciagent-wizard` — `generators/copilot.py`, `generators/profiles.py`

### Summary

The wizard's Copilot plugin generator (`generators/copilot.py`) had two problems inherited from the core repo that were already fixed in `build_plugin.py`:

1. **Fullstack tool references baked into output** — The `_RIGOR_GUARDRAIL_INSTRUCTIONS` constant directed agents to never use the terminal and to route all analysis through `execute_code`. Wizard-generated plugins target VS Code Copilot, which has no `execute_code` tool, making these instructions confusing and incorrect.

2. **Rigor duplication** — `scientific_rigor.md` appeared in every agent's `_AGENT_PROMPT_MAP` list AND was inlined via the `_RIGOR_LINK_PATTERN` replacement, producing 2 copies per individual agent and 3 copies per merged agent (compact profile).

### Files Changed

#### `src/sciagent_wizard/generators/copilot.py`

##### Modified: `_RIGOR_GUARDRAIL_INSTRUCTIONS`

Replaced fullstack-specific terminal prohibition and `execute_code` confirmation flow with platform-agnostic terminal usage guidance matching the updated core templates.

**Before:**
```python
_RIGOR_GUARDRAIL_INSTRUCTIONS = """\
### Scientific Rigor — Shell / Terminal Policy

**NEVER** use the `terminal` tool to execute data analysis or computation code.
All analysis must go through the provided analysis tools (e.g. `execute_code`)
which enforce scientific rigor checks automatically.

The `terminal` tool may be used **only** for environment setup tasks such as
`pip install`, `git` commands, or opening files — and only after describing the
command to the user.

If a rigor warning is raised by `execute_code` (indicated by
`needs_confirmation: true` in the result), you **MUST**:
1. Present the warnings to the user verbatim.
2. Ask whether to proceed.
3. If confirmed, re-call `execute_code` with `confirmed: true`.
4. Never silently bypass or suppress rigor warnings.
"""
```

**After:**
```python
_RIGOR_GUARDRAIL_INSTRUCTIONS = """\
### Scientific Rigor — Terminal Usage

Use the terminal for running Python scripts, installing packages, and
environment setup.  Always describe what a terminal command will do
before running it.  Prefer writing scripts to files and executing them
over inline terminal commands for complex analyses.

When analysis produces unexpected, suspicious, or boundary-case results,
flag them prominently to the user and ask for confirmation before
proceeding.  Never silently ignore anomalous results or warnings.
"""
```

##### Modified: `_AGENT_PROMPT_MAP`

Removed `"scientific_rigor.md"` from every agent's prompt list. The inline link-replacement (`_RIGOR_LINK_PATTERN`) remains as the single injection point — identical to the change already applied in `build_plugin.py`.

**Before (every entry had it):**
```python
"coordinator": ["scientific_rigor.md", "communication_style.md", "clarification.md"],
"coder": ["scientific_rigor.md", "communication_style.md", "code_execution.md", ...],
```

**After:**
```python
"coordinator": ["communication_style.md", "clarification.md"],
"coder": ["communication_style.md", "code_execution.md", ...],
```

##### Modified: `_merge_agent_bodies()`

Added `rigor_inlined` flag so only the first source in a merged agent gets the full rigor text; subsequent sources get a back-reference. Mirrors the same change in `build_plugin.py`.

**Before:**
```python
body_parts: list[str] = []
for src_name in sources:
    ...
    if rigor_text:
        replacement_block = (
            "### Shared Scientific Rigor Principles\n\n" + rigor_text
        )
        body = _RIGOR_LINK_PATTERN.sub(replacement_block, body)
    body_parts.append(body.strip())
```

**After:**
```python
body_parts: list[str] = []
rigor_inlined = False
for src_name in sources:
    ...
    if rigor_text:
        if not rigor_inlined:
            replacement_block = (
                "### Shared Scientific Rigor Principles\n\n" + rigor_text
            )
            body = _RIGOR_LINK_PATTERN.sub(replacement_block, body)
            rigor_inlined = True
        else:
            body = _RIGOR_LINK_PATTERN.sub(
                "See *Shared Scientific Rigor Principles* above.", body,
            )
    body_parts.append(body.strip())
```

#### `src/sciagent_wizard/generators/profiles.py`

##### Modified: `REVIEWER_PROMPT_MODULES`

Removed `"scientific_rigor.md"` — the merged `reviewer` agent now receives rigor only through inline link-replacement.

**Before:**
```python
REVIEWER_PROMPT_MODULES: list[str] = [
    "scientific_rigor.md",
    "communication_style.md",
    "clarification.md",
]
```

**After:**
```python
REVIEWER_PROMPT_MODULES: list[str] = [
    "communication_style.md",
    "clarification.md",
]
```

### Wizard Output Results

| Agent file | Rigor copies before | After |
|-----------|---------------------|-------|
| Individual agents (coordinator, coder, etc.) | 2 copies | 1 copy (inline only) |
| Merged reviewer (compact profile) | 3 copies | 1 copy + back-reference |
| `_RIGOR_GUARDRAIL_INSTRUCTIONS` | Fullstack-specific | Platform-agnostic |

### Alignment with Core Repo

These changes bring the wizard's `copilot.py` into parity with the core `build_plugin.py`:

| Concern | `build_plugin.py` | `copilot.py` (before) | `copilot.py` (after) |
|---------|-------------------|----------------------|---------------------|
| `scientific_rigor.md` in prompt map | Removed | Still present | Removed |
| Merged agent rigor dedup | `rigor_inlined` flag | No dedup | `rigor_inlined` flag |
| Terminal/tool policy | Generic terminal usage | `execute_code`-specific | Generic terminal usage |

---

## Testing

- All 52 non-live tests pass (`pytest tests/ -m "not live"`)
- Verified with full profile + prefix, compact profile + prefix, and default prefix builds

---

## Changelog: Multi-Domain Switching (`/switch-domain`)

**Date:** 2026-03-15
**Scope:** `sciagent` core — templates, skills, agents, build pipeline

### Summary

SciAgent previously supported only a single domain configuration per workspace (`docs/domain/`). Researchers who work across related-but-distinct domains (e.g. intracellular vs. extracellular neurophysiology) had to manually reconfigure each time.

This change introduces multi-domain support: domain knowledge is stored in `docs/domains/<slug>/` directories managed by a `manifest.yaml` registry. A new `/switch-domain` skill hot-swaps all domain-specific content — docs, template links, and per-library skills — while leaving core SciAgent skills untouched. The existing `/configure-domain` and `/update-domain` skills are updated to write to the new multi-domain directory structure.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Concurrent domains | One active at a time | Simpler implementation; avoids conflicting guidance |
| Swap scope | Full swap (docs + skills) | Domain-expertise and per-library skills swap together with template links |
| Storage layout | `docs/domains/<slug>/` + `manifest.yaml` | Directory-per-domain with centralized registry; self-contained for portability |
| Python runtime | Not required | All skills are pure agent-driven (file editing only) |
| Legacy compat | Opt-in migration | `docs/domain/` detected → user prompted → one-time move to `docs/domains/<slug>/` |

### Manifest Schema

New file: `docs/domains/manifest.yaml`

```yaml
active: intracellular-ephys          # slug of the currently loaded domain
domains:
  intracellular-ephys:
    display_name: "Intracellular Electrophysiology (Patch-Clamp)"
    created: "2026-03-15"
    packages:
      - pyabf
      - neo
      - elephant
      - efel
    file_formats: [.abf, .nwb, .csv]
    description: >-
      Whole-cell and cell-attached patch-clamp recordings of cortical
      neurons — action potentials, synaptic currents, passive properties.
  extracellular-ephys:
    display_name: "Extracellular Electrophysiology"
    created: "2026-03-15"
    packages:
      - spikeinterface
      - neo
      - elephant
    file_formats: [.nwb, .mda, .bin]
    description: >-
      Multi-electrode array and silicon probe recordings — spike sorting,
      LFP analysis, population dynamics.
```

### Per-Domain Directory Layout

```
docs/domains/
├── manifest.yaml
├── intracellular-ephys/
│   ├── operations.md
│   ├── workflows.md
│   ├── library-api.md
│   ├── tools.md
│   ├── skills.md
│   └── skills/                    # Skill content source-of-truth
│       ├── domain-expertise/
│       │   └── SKILL.md
│       ├── pyabf/
│       │   └── SKILL.md
│       └── neo/
│           └── SKILL.md
└── extracellular-ephys/
    ├── operations.md
    ├── ...
    └── skills/
        ├── domain-expertise/
        │   └── SKILL.md
        └── spikeinterface/
            └── SKILL.md
```

The `skills/` subdirectory within each domain stores the **source of truth** for domain-specific skill content. During a switch, these files are copied into the workspace's active `skills/` directory.

---

### Files Changed

#### Created: `templates/skills/switch-domain/SKILL.md`

New user-invokable skill with a 7-step procedure:

1. **Read manifest** — Parse `docs/domains/manifest.yaml`. If missing, check for legacy `docs/domain/` and offer one-time migration (Step 1b).
2. **List domains** — Display table with slug, display name, package list, and active indicator.
3. **Preview diff** — Show packages added/removed, skills being swapped, template links being rewritten. Warn about unsaved changes.
4. **Swap domain doc links** — In all template and `.instructions.md` files, rewrite Markdown links from `docs/domains/<old>/` → `docs/domains/<new>/`. Preserve markers and anchor fragments.
5. **Swap skill files** — Copy target domain's `skills/` content into workspace's active skill location. Remove old-domain-only skill directories. Never remove non-domain skills.
6. **Update manifest** — Set `active: <target-slug>`.
7. **Verify** — Re-scan to confirm all links point to new domain. Summarize changes.

Includes legacy migration sub-procedure (Step 1b): detect `docs/domain/` → ask for slug → move files → create manifest → rewrite links.

Includes explicit **non-domain skills list** that must never be swapped:
`analysis-planner`, `code-reviewer`, `configure-domain`, `data-qc`, `docs-ingestor`, `report-writer`, `rigor-reviewer`, `scientific-rigor`, `switch-domain`, `update-domain`.

YAML frontmatter:
```yaml
---
name: switch-domain
description: >-
  Switch between configured research domains — lists available domains,
  previews the target, and hot-swaps all domain-specific content (docs,
  skills, template links).
argument-hint: Domain to switch to, e.g. "extracellular-ephys" or run without args to list available domains
user-invokable: true
---
```

---

#### Modified: `templates/skills/configure-domain/SKILL.md`

##### Added: Step 1b — Choose Domain Slug

New step after the interview. Asks user for a kebab-case slug (3–40 chars, lowercase + hyphens, unique across existing domains) and a display name. Checks `docs/domains/manifest.yaml` for conflicts.

##### Modified: Step 2 — Audit Templates

Now checks `docs/domains/manifest.yaml` for existing domains and falls back to legacy `docs/domain/` detection.

**Before:**
```markdown
3. Also check whether `docs/domain/` already exists with domain
   knowledge files from a previous run.
```

**After:**
```markdown
3. Check whether `docs/domains/manifest.yaml` exists.  If it does,
   read it to see which domains are already configured.
   Also check for legacy `docs/domain/` (without the `s`) from an
   older single-domain setup.
```

##### Modified: Step 4 — Fill Template Placeholders

All `docs/domain/` paths → `docs/domains/<slug>/`. Added per-package skill storage paths and `domain-expertise` skill.

**Before:**
```markdown
**Domain docs structure** — create one file per template in `docs/domain/`:
- `docs/domain/operations.md` — ...
- `docs/domain/workflows.md` — ...
- `docs/domain/library-api.md` — ...
- `docs/domain/tools.md` — ...
- `docs/domain/skills.md` — ...
```

**After:**
```markdown
**Domain docs structure** — create one file per template in
`docs/domains/<slug>/` (using the slug from Step 1b):
- `docs/domains/<slug>/operations.md` — ...
- `docs/domains/<slug>/workflows.md` — ...
- `docs/domains/<slug>/library-api.md` — ...
- `docs/domains/<slug>/tools.md` — ...
- `docs/domains/<slug>/skills.md` — ...
- `docs/domains/<slug>/skills/domain-expertise/SKILL.md` — Auto-loading domain expertise
- `docs/domains/<slug>/skills/<package>/SKILL.md` — Per-package API skills
```

Link example updated:
```markdown
See [domain workflows](docs/domains/intracellular-ephys/operations.md#standard-workflows)
```

##### Modified: Step 6 — Lite Docs

Docs written to `docs/domains/<slug>/` instead of `docs/`. Per-package skill files also created at `docs/domains/<slug>/skills/<package>/SKILL.md` and copied to workspace `skills/`.

##### Added: Step 7b — Update Domain Manifest

New step: create or update `docs/domains/manifest.yaml` with the new domain's metadata (display name, created date, packages, file formats, description). Sets `active: <slug>`. Preserves existing domain entries.

##### Modified: Re-Run Safety

**Before:** Checks `docs/domain/` for existing content.

**After:** Checks `docs/domains/manifest.yaml` first. If manifest exists with domains, asks "Create a new domain or update existing `<active-slug>`?" Suggests `/update-domain` for updates. Legacy `docs/domain/` migration offered via `/switch-domain`.

##### Modified: "What This Skill Does NOT Do"

Updated `docs/domain/` → `docs/domains/<slug>/` in the reference.

---

#### Modified: `templates/skills/update-domain/SKILL.md`

##### Modified: Step 2 — Audit Current State

Now reads `docs/domains/manifest.yaml` to identify active domain directory. Falls back to `docs/domain/` for legacy setups. Displays active domain slug in the briefing. Added tip: "To update a non-active domain, first run `/switch-domain <slug>` then `/update-domain`."

**Before:**
```markdown
3. Check `docs/domain/` for existing domain knowledge files from a
   previous `/configure-domain` run.
...
5. Brief the user: "Here's your current configuration in the affected
   files.  I'll update X and Y."
```

**After:**
```markdown
3. Check `docs/domains/manifest.yaml` to identify the active domain
   and its directory (`docs/domains/<active-slug>/`).  If the
   manifest does not exist, fall back to checking `docs/domain/` for
   legacy single-domain setups.
...
5. Brief the user: "Here's your current configuration in the affected
   files (active domain: `<slug>`).  I'll update X and Y."

> **Tip:** To update a non-active domain, first run
> `/switch-domain <slug>` to make it active, then `/update-domain`.
```

##### Modified: Step 5 — Apply Updates

All `docs/domain/` paths → `docs/domains/<slug>/`. Added per-package skill creation at `docs/domains/<slug>/skills/<package>/SKILL.md`. Added manifest update after package/format changes.

**Before:**
```markdown
- **Adding a package**: Update `docs/domain/library-api.md` ...
  `docs/domain/tools.md` ... `docs/domain/operations.md` ...
```

**After:**
```markdown
- **Adding a package**: Update `docs/domains/<slug>/library-api.md` ...
  `docs/domains/<slug>/tools.md` ... `docs/domains/<slug>/operations.md` ...
  Also create `docs/domains/<slug>/skills/<package>/SKILL.md` ...

After applying changes, update the domain's entry in
`docs/domains/manifest.yaml` if packages or file formats changed.
```

---

#### Modified: `templates/agents/.github/agents/domain-assembler.agent.md`

##### Modified: YAML frontmatter description

Added `/switch-domain` to the listed skills.

**Before:**
```yaml
description: >-
  ...Invoke directly or via /configure-domain and /update-domain skills.
```

**After:**
```yaml
description: >-
  ...Invoke directly or via /configure-domain, /update-domain, and
  /switch-domain skills.
```

##### Modified: Auto-Detection

Added multi-domain awareness. When `docs/domains/manifest.yaml` exists with multiple domains, the agent now prompts:

```markdown
> "You have N domains configured (active: `<slug>`).  Would you like
> to switch domains (`/switch-domain`), update the current one
> (`/update-domain`), or add a new domain (`/configure-domain`)?"
```

##### Modified: Step 2 (Audit templates)

Now also checks `docs/domains/manifest.yaml` for existing domains.

##### Modified: Step 4 (Fill placeholders)

All `docs/domain/` paths → `docs/domains/<slug>/`. Link example updated.

##### Added: Steps 7–8 (Update manifest + Verify)

Step 7 creates/updates `docs/domains/manifest.yaml`. Step 8 is the verify step (previously step 7).

##### Added: Workflow — Switch Domain (`/switch-domain`)

New section between "Full Configuration" and "Incremental Update":

```markdown
### Workflow: Switch Domain (`/switch-domain`)

1. Read `docs/domains/manifest.yaml` to list available domains
2. Preview the diff (packages added/removed, skills being swapped)
3. Rewrite template links from `docs/domains/<old>/` → `docs/domains/<new>/`
4. Swap domain-expertise and per-package skill files
5. Update `active` in manifest
6. Verify all links point to the new domain
```

##### Modified: Placeholder Pattern section

`docs/domain/` → `docs/domains/<slug>/` in the instruction.

##### Modified: Re-Run Safety

Added manifest detection, legacy migration via `/switch-domain`, and "new domain vs. update existing" prompt.

---

#### Modified: `templates/agents/.claude/agents/domain-assembler.md`

Mirror of all changes to the GitHub agent:
- Multi-domain auto-detection prompt
- `docs/domain/` → `docs/domains/<slug>/` throughout
- Added Switch Domain workflow section
- Steps 7–8 (manifest update + verify)
- Manifest-aware re-run safety with legacy migration

---

#### Modified: `templates/AGENTS.md`

Updated "Domain Setup" section:

**Before:**
```markdown
## Domain Setup

If template files still contain `<!replace ...>` markers ...
Domain knowledge will be placed in `docs/domain/` with links from the template files.
```

**After:**
```markdown
## Domain Setup

If template files still contain `<!replace ...>` markers ...
Domain knowledge will be placed in `docs/domains/<slug>/` with links from the template files.

SciAgent supports **multiple configured domains**.  Use
`/switch-domain` to swap between them (e.g. intracellular vs.
extracellular electrophysiology), or `/update-domain` to refine the
currently active domain.  Domain configuration is tracked in
`docs/domains/manifest.yaml`.
```

---

#### Modified: `templates/skills.md`

Added `switch-domain` row to the default skills table:

```markdown
| Switch Domain | `skills/switch-domain/` | Switch between configured research domains — hot-swaps docs, skills, and template links | `/switch-domain` |
```

---

#### Modified: `templates/builtin_agents.md`

Updated Domain Assembler description:
- `docs/domain/` → `docs/domains/<slug>/` in description and capabilities
- `docs/` → `docs/domains/<slug>/` for API references
- Skills count: "two user-invokable skills" → "three user-invokable skills"
- Added `/switch-domain` to skills list

---

#### Modified: `templates/operations.md`

Updated placeholder detection guidance to mention `/switch-domain` for multi-domain setups:

**Before:**
```markdown
Domain knowledge will be created in `docs/domain/` with links from the template files.
```

**After:**
```markdown
Domain knowledge will be created in `docs/domains/<slug>/` with links from the template files.
If multiple domains are already configured, suggest `/switch-domain`
to swap between them.
```

---

#### Modified: `scripts/build_plugin.py`

##### Modified: `PROFILES["compact"]["exclude_skills"]`

Added `"switch-domain"` to the exclusion list (alongside `"update-domain"`):

**Before:**
```python
"exclude_skills": ["update-domain"],
```

**After:**
```python
"exclude_skills": ["update-domain", "switch-domain"],
```

##### Modified: `PROFILES["compact"]["merge_skills"]["configure-domain"]`

Added `"switch-domain"` to the merged `configure-domain` skill sources:

**Before:**
```python
"configure-domain": {
    "sources": ["configure-domain", "update-domain"],
    "description": None,
    "section_titles": {
        "configure-domain": None,
        "update-domain": "Incremental Update Mode",
    },
},
```

**After:**
```python
"configure-domain": {
    "sources": ["configure-domain", "update-domain", "switch-domain"],
    "description": None,
    "section_titles": {
        "configure-domain": None,
        "update-domain": "Incremental Update Mode",
        "switch-domain": "Domain Switching Mode",
    },
},
```

In the compact profile, `switch-domain` is excluded as a standalone skill but its content is merged into the `configure-domain` skill under a "Domain Switching Mode" section header.

---

### Wizard Impact Notes

The wizard (`sciagent-wizard`) generates domain-specific output via several generators. The following changes are needed to align the wizard with the new multi-domain structure:

#### `src/sciagent_wizard/generators/copilot.py`

1. **`_domain_expertise_skill_md()`** — Currently writes to `skills/domain-expertise/SKILL.md`. Should also write the source-of-truth copy to `docs/domains/<slug>/skills/domain-expertise/SKILL.md` so it can be restored during domain switches.

2. **`_package_skill_md()`** — Per-package skills (e.g. `skills/pyabf/SKILL.md`) should also be written to `docs/domains/<slug>/skills/<package>/SKILL.md`.

3. **`_compile_agents_from_templates()`** — When rendering domain doc links in coordinator/agent bodies, use `docs/domains/<slug>/` instead of `docs/domain/`. The `render_docs_with_domain_links()` helper should be updated.

4. **`generate_copilot_project()`** / **`generate_copilot_plugin()`** — Should create `docs/domains/manifest.yaml` with the single domain configured during wizard generation. This ensures the output is immediately compatible with `/switch-domain` if the user later configures a second domain.

5. **Profile handling** — The compact profile `merge_skills` spec now includes `"switch-domain"` as a third source for the merged `configure-domain` skill. If the wizard applies profile-based filtering, update accordingly.

#### `src/sciagent_wizard/generators/fullstack.py`

- The fullstack generator (`generate_fullstack_project()`) creates `domain_prompt.py` with `DOMAIN_EXPERTISE`. This is loaded at Python runtime (not via file links), so multi-domain switching would require a different mechanism (e.g. multiple `domain_prompt_*.py` files with a config selector). **Defer for now** — fullstack agents are single-domain; multi-domain is a workspace-level concern managed by the skill-based workflow.

#### `src/sciagent_wizard/rendering.py`

- The `render_template()` function substitutes `<!-- REPLACE: ... -->` placeholders. If any template references `docs/domain/`, the rendering context should use `docs/domains/<slug>/` instead. Check whether `_build_context()` emits domain paths.

#### `src/sciagent_wizard/models.py`

- Consider adding a `domain_slug: str` field to `WizardState` (default: derived from `agent_name` or `domain_description`). This would flow through to generators that create domain directories and the manifest.

### Manifest Creation in Wizard Output

When the wizard generates a Copilot plugin or project, it should emit:

```yaml
# docs/domains/manifest.yaml
active: <slug>
domains:
  <slug>:
    display_name: <state.agent_display_name or state.domain_description>
    created: <generation date>
    packages: <list of confirmed package names from state.confirmed_packages>
    file_formats: <state.file_types>
    description: <state.domain_description>
```

This ensures wizard-generated projects are immediately multi-domain-ready without requiring the user to run `/configure-domain` again.

---

### Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Workspace with `docs/domain/` (no manifest) | `/switch-domain` and `/configure-domain` detect legacy layout and offer one-time migration |
| Workspace with no domain configured | `/switch-domain` tells user to run `/configure-domain` first |
| Workspace with `docs/domains/manifest.yaml` (single domain) | All skills work normally; `/switch-domain` lists 1 domain and suggests adding another |
| Workspace with `docs/domains/manifest.yaml` (multiple domains) | Full multi-domain switching available |
| Wizard-generated output (pre-update) | Uses `docs/domain/` — triggers legacy migration on first `/switch-domain` invocation |
| Wizard-generated output (post-update) | Uses `docs/domains/<slug>/` + manifest — immediately multi-domain-ready |

### Non-Domain Skills (Protected During Switch)

These skills are **never** removed, swapped, or modified during a domain switch:

- `analysis-planner`
- `code-reviewer`
- `configure-domain`
- `data-qc`
- `docs-ingestor`
- `report-writer`
- `rigor-reviewer`
- `scientific-rigor`
- `switch-domain`
- `update-domain`
