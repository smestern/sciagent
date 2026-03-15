---
name: switch-domain
description: >-
  Switch between configured research domains — lists available domains,
  previews the target, and hot-swaps all domain-specific content (docs,
  skills, template links). Use after configuring multiple domains with
  /configure-domain.
argument-hint: Domain to switch to, e.g. "extracellular-ephys" or run without args to list available domains
user-invokable: true
---

# Switch Domain

Hot-swap the active research domain.  SciAgent supports multiple
configured domains stored under `docs/domains/<slug>/`.  This skill
lists them, previews the diff, and rewrites all template links and
skill files to point at the chosen domain.

## When to Use

- You have configured two or more domains via `/configure-domain` and
  want to swap between them.
- You are starting a different type of analysis that requires a
  different set of packages, workflows, and guardrails.
- Another agent or user mentioned `/switch-domain`.

## Prerequisites

- At least two domains must exist under `docs/domains/` with a
  `docs/domains/manifest.yaml` file.
- If only `docs/domain/` exists (legacy single-domain layout), this
  skill will offer to migrate it first (see Step 1b).

## Manifest Schema

The domain registry lives at `docs/domains/manifest.yaml`:

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
docs/domains/<slug>/
├── operations.md          # Workflows, parameters, edge cases, precision
├── workflows.md           # Workflow overview, individual workflow sections
├── library-api.md         # Core classes, key functions, pitfalls, recipes
├── tools.md               # Domain tool documentation
├── skills.md              # Domain-specific skill entries
└── skills/                # Skill SKILL.md source-of-truth files
    ├── domain-expertise/
    │   └── SKILL.md        # Auto-loading domain context
    ├── pyabf/
    │   └── SKILL.md        # Per-package API skill
    └── ...
```

The `skills/` subdirectory stores the **source of truth** for
domain-specific skill content.  During a switch, these files are copied
into the workspace's active `skills/` directory (e.g.
`.github/skills/` or the plugin's `skills/` folder).

## Procedure

### Step 1 — Read Manifest

1. Look for `docs/domains/manifest.yaml`.
2. If it exists, parse it and read the `active` slug and the list of
   configured domains.  Proceed to Step 2.
3. If it does **not** exist, check for legacy `docs/domain/`.  If found,
   offer migration (Step 1b).  If neither exists, tell the user to run
   `/configure-domain` first.

#### Step 1b — Legacy Migration (one-time)

If `docs/domain/` exists but `docs/domains/manifest.yaml` does not:

1. Ask the user for a **kebab-case slug** and **display name** for their
   existing domain — e.g. slug `intracellular-ephys`, display name
   "Intracellular Electrophysiology".
2. Create `docs/domains/<slug>/` and move all files from `docs/domain/`
   into it.
3. If domain-specific skill files exist in the workspace `skills/`
   directory (e.g. `skills/domain-expertise/SKILL.md`, per-package
   skills), copy them into `docs/domains/<slug>/skills/`.
4. Create `docs/domains/manifest.yaml` with the migrated domain as
   `active`.
5. Rewrite template links from `docs/domain/` →
   `docs/domains/<slug>/` in all template and instruction files.
6. Confirm: "Migrated your existing domain to
   `docs/domains/<slug>/`.  You can now run `/configure-domain` to add
   a second domain, then `/switch-domain` to swap between them."

### Step 2 — List Available Domains

Display the domains in a table:

| # | Slug | Display Name | Packages | Active |
|---|------|-------------|----------|--------|
| 1 | `intracellular-ephys` | Intracellular Electrophysiology | pyabf, neo, elephant, efel | ✓ |
| 2 | `extracellular-ephys` | Extracellular Electrophysiology | spikeinterface, neo, elephant | |

If the user invoked the skill without specifying a domain, ask which
domain to switch to.

If the requested domain is already active, inform the user and stop:
"Domain `<slug>` is already active.  Nothing to switch."

### Step 3 — Preview Diff

Before switching, show the user what will change:

1. **Packages** — List packages being added and removed:
   - Added: `spikeinterface`
   - Removed: `pyabf`, `efel`
   - Shared: `neo`, `elephant`
2. **Skills** — List skill directories being swapped:
   - Added: `skills/spikeinterface/`
   - Removed: `skills/pyabf/`, `skills/efel/`
   - Updated: `skills/domain-expertise/` (content changes)
   - Unchanged: `skills/neo/`, `skills/elephant/`
3. **Template links** — Note which files will have their `docs/domains/`
   links rewritten.
4. **Warning** — If the current domain has unsaved changes (files in
   `docs/domains/<current>/` modified more recently than the manifest),
   warn: "Your current domain docs have been modified since last switch.
   These changes are preserved in `docs/domains/<current>/`."

Ask the user to confirm: "Switch from `<current>` to `<target>`?"

### Step 4 — Swap Domain Doc Links

For each template and instruction file in the workspace:

1. Search for Markdown links containing `docs/domains/<current-slug>/`
   (or legacy `docs/domain/`).
2. Replace the path portion with `docs/domains/<target-slug>/`.
3. Keep the marker above the link untouched.
4. Keep the anchor fragment (e.g. `#standard-workflows`) untouched.

**Files to check** (non-exhaustive — scan the workspace):
- `operations.md`, `workflows.md`, `tools.md`, `library_api.md`,
  `skills.md`
- `.github/instructions/*.instructions.md`
- `AGENTS.md`

**Example** — before:
```
See [domain workflows](docs/domains/intracellular-ephys/operations.md#standard-workflows)
```
After:
```
See [domain workflows](docs/domains/extracellular-ephys/operations.md#standard-workflows)
```

### Step 5 — Swap Skill Files

1. Read the target domain's `docs/domains/<target>/skills/` directory.
2. For each skill directory found there:
   a. Copy `SKILL.md` into the workspace's active skill location
      (e.g. `skills/<name>/SKILL.md` or `.github/skills/<name>/SKILL.md`).
   b. Overwrite the existing SKILL.md for that skill name.
3. For each skill that existed in the **old** domain but does **not**
   exist in the **new** domain:
   a. Remove the skill directory from the workspace's active skill
      location.
   b. Only remove skills that are listed in the old domain's manifest
      `packages` — **never** remove non-domain skills (analysis-planner,
      data-qc, report-writer, scientific-rigor, code-reviewer,
      rigor-reviewer, docs-ingestor, configure-domain, update-domain,
      switch-domain).
4. The `domain-expertise` skill always exists in both domains but with
   different content — overwrite it with the target domain's version.

### Step 6 — Update Manifest

1. Set `active: <target-slug>` in `docs/domains/manifest.yaml`.
2. Write the updated YAML back to disk.

### Step 7 — Verify

1. Re-scan template files to confirm all `docs/domains/` links point
   to `<target-slug>`.
2. Confirm that `skills/domain-expertise/SKILL.md` matches the target
   domain's version.
3. List per-package skills present in the workspace `skills/` directory
   and confirm they match the target domain's package list.
4. Summarize:
   - Domain switched from `<old>` → `<new>`
   - N template links rewritten across M files
   - Skills added: ...
   - Skills removed: ...
   - Skills updated: ...

## Non-Domain Skills (Never Swapped)

The following skills are part of SciAgent's core and are **never**
removed or modified during a domain switch:

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

## Re-Run Safety

- **Idempotent** — Switching to the already-active domain is a no-op.
- **Reversible** — Switching back restores the previous domain's content
  from `docs/domains/<slug>/`.  No data is lost.
- **Domain isolation** — Changes to one domain's docs are stored in its
  own directory and are never overwritten by a switch.  Each domain's
  `docs/domains/<slug>/` is its own source of truth.

## What This Skill Does NOT Do

- Does **not** execute Python code or run analysis
- Does **not** install or uninstall packages (suggest `pip install`
  commands if the target domain has packages not yet installed)
- Does **not** require `sciagent[wizard]` — works with file editing
  tools only
- Does **not** create new domains — use `/configure-domain` for that
- Does **not** merge or layer domains — strictly one active domain at
  a time

## Domain Customization

<!-- Add domain-specific switching notes below this line.
     Examples:
     - Domains that should always be available
     - Post-switch validation steps for this domain
     - Environment variables or settings that change per domain
-->
