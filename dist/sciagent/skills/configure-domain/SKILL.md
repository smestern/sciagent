---
name: configure-domain
description: First-time domain setup — interviews you about your research field, discovers relevant scientific packages via PyPI and GitHub, then fills in all template placeholder sections across your SciAgent instruction files. No Python runtime or wizard dependency needed.
argument-hint: Describe your research domain, e.g. "electrophysiology patch-clamp analysis" or "single-cell RNA-seq"
user-invokable: true
---

# Configure Domain Knowledge

Set up your SciAgent installation for a specific research domain.  This
skill walks you through a structured interview, discovers relevant
scientific packages, and fills in the `<!-- REPLACE: ... -->` placeholder
sections across your template files — turning generic SciAgent
instructions into domain-tuned guidance.

## When to Use

- You just installed SciAgent templates and the instruction files still
  contain unfilled `<!-- REPLACE: ... -->` placeholder comments.
- You want to configure SciAgent for a new research domain from scratch.
- You already have one domain configured and want to add a second
  (e.g. switching between intracellular and extracellular ephys).
- Another agent suggested running `/configure-domain` because it
  detected unfilled placeholders.

## Procedure

### Step 1 — Interview

Ask the user about their research domain.  Gather the following
information through natural conversation (do not present this as a
rigid questionnaire — adapt based on answers):

1. **Research domain & sub-field** — e.g. "cellular electrophysiology,
   specifically patch-clamp recordings of cortical neurons"
2. **Data types & file formats** — e.g. ".abf files, .csv spike tables,
   .nwb bundles"
3. **Existing packages already in use** — e.g. "we already use pyabf,
   neo, and elephant"
4. **Analysis goals** — e.g. "spike detection, AP feature extraction,
   dose-response fitting"
5. **Common workflows** — e.g. "load ABF → extract sweeps → detect
   spikes → measure features → compare across conditions"
6. **Value ranges & units** — e.g. "membrane potential –100 to +60 mV,
   currents –2000 to 2000 pA"

Confirm your understanding back to the user before proceeding.

### Step 1b — Choose Domain Slug

After gathering domain information, ask the user for a **kebab-case
slug** to identify this domain — e.g. `intracellular-ephys`,
`single-cell-rnaseq`, `proteomics-ms`.  Auto-suggest a slug
from the domain keywords.

Rules for slugs:
- Lowercase letters, digits, and hyphens only
- No spaces, underscores, or special characters
- 3–40 characters
- Must be unique across existing domains (check `docs/domains/manifest.yaml`)

Also ask for a short **display name** (e.g. "Intracellular
Electrophysiology (Patch-Clamp)").

### Step 2 — Audit Templates

Scan the workspace for SciAgent instruction files and identify unfilled
placeholders:

1. Search for files matching `*.instructions.md`, `operations.md`,
   `workflows.md`, `tools.md`, `library_api.md`, `skills.md` in
   `.github/instructions/` and the workspace root.
2. In each file, look for `<!replace ... --->` markers (or legacy
   `<!-- REPLACE: key — description -->` comments).
3. Check whether `docs/domains/manifest.yaml` exists.  If it does,
   read it to see which domains are already configured.
   Also check for legacy `docs/domain/` (without the `s`) from an
   older single-domain setup.
4. Build a checklist of every unfilled placeholder found, grouped by
   file.
5. Show the checklist to the user: "I found N unfilled placeholders
   across M files.  Here's what needs filling: ..."

### Step 3 — Discover Packages

Based on the interview answers, search for relevant scientific Python
packages:

1. Formulate 2–3 targeted search queries from the domain keywords
   (e.g. "electrophysiology patch clamp python", "ABF file analysis
   python", "spike sorting library python").
2. For each query, fetch the PyPI JSON API:
   `https://pypi.org/pypi/{candidate_name}/json` for known package
   names the user mentioned or that are commonly associated with
   the domain.
3. For packages with GitHub repositories, fetch the README to get a
   quick overview of capabilities.
4. Present discovered packages to the user with:
   - Package name and version
   - One-line description
   - Repository URL (if available)
   - Relevance to their stated goals

Ask the user to confirm which packages to include.

### Step 4 — Fill Template Placeholders

For each confirmed placeholder, **do not** inline the full domain content
into the template file.  Instead, create separate domain knowledge files
and insert links.

**Domain docs structure** — create one file per template in
`docs/domains/<slug>/` (using the slug from Step 1b):

- `docs/domains/<slug>/operations.md` — Standard workflows, analysis
  parameters, parameter adjustment guidance, edge cases, reporting
  precision table
- `docs/domains/<slug>/workflows.md` — Workflow overview table,
  individual workflow sections with steps, parameters, and expected
  outputs
- `docs/domains/<slug>/library-api.md` — Core classes, key functions,
  common pitfalls, and quick-start recipes for confirmed packages
- `docs/domains/<slug>/tools.md` — Domain tool documentation and
  custom tool templates
- `docs/domains/<slug>/skills.md` — Domain-specific skill entries
  (if any custom skills are warranted by the domain)
- `docs/domains/<slug>/skills/domain-expertise/SKILL.md` — Auto-loading
  domain expertise skill content
- `docs/domains/<slug>/skills/<package>/SKILL.md` — Per-package API
  skill content for each confirmed package

**For each placeholder:**

1. Read the marker description to understand the expected content —
   each `<!replace --- description --- or add a link--->` (or legacy
   `<!-- REPLACE: key — description. Example: ... -->`) includes
   guidance on the expected format.
2. Write the domain-appropriate content under a Markdown heading in the
   corresponding `docs/domains/<slug>/<template>.md` file.  Use headings
   that match the placeholder description (e.g. `## Standard Workflows`,
   `## Analysis Parameters`).
3. Insert a Markdown link **below** the marker in the template file
   pointing to the relevant section.  Keep the marker itself intact.

**Example** — before:
```
<!replace --- Step-by-step workflows specific to your domain --- or add a link--->
```

After assembly:
```
<!replace --- Step-by-step workflows specific to your domain --- or add a link--->

See [domain workflows](docs/domains/intracellular-ephys/operations.md#standard-workflows)
```

The full workflow content lives in
`docs/domains/<slug>/operations.md` under a `## Standard Workflows`
heading.

**Fill order** (adjust based on which files have placeholders):

1. `operations.md`
2. `workflows.md`
3. `library_api.md`
4. `tools.md`
5. `skills.md`

### Step 5 — Append Domain-Specific Content

Beyond filling placeholders, add new content where warranted:

- **Domain guardrails** — Add forbidden patterns or warning patterns
  specific to the domain (e.g. "never average across conditions before
  checking for outliers")
- **Additional workflows** — If the domain has standard pipelines not
  covered by the placeholder structure
- **Custom skills** — If the domain warrants specialized skill entries

Append new content below the existing sections — never overwrite content
that was already present before this session.

### Step 6 — Lite Docs (Optional)

For each confirmed package, offer to create a minimal API reference:

1. Fetch the package's PyPI metadata via
   `https://pypi.org/pypi/{name}/json`
2. If a GitHub repository is listed, fetch the README
3. Write a condensed reference to the
   `docs/domains/<slug>/` directory following the `library_api.md`
   format (Core Classes, Key Functions, Common Pitfalls, Quick-Start
   Recipes)
4. Also write per-package skill content to
   `docs/domains/<slug>/skills/<package>/SKILL.md` for each confirmed
   package, and copy it into the workspace's active `skills/` directory.

For deeper documentation crawling, suggest the user invoke
`/docs-ingestor` (requires `sciagent[wizard]`).

### Step 7 — Verify

1. Re-scan all template files for remaining `<!replace ...>` markers
   without links below them.
2. Verify that `docs/domains/<slug>/` files were created with the
   expected content.
3. Summarize what was changed:
   - Files modified (with placeholder counts before/after)
   - Domain docs created
   - Packages included
   - New sections added
4. If any placeholders remain unfilled (e.g. the user deferred some),
   note them and suggest running `/update-domain` later.

### Step 7b — Update Domain Manifest

After creating all domain files:

1. If `docs/domains/manifest.yaml` does not exist, create it.
2. Add an entry for the new domain with:
   - `display_name` — from Step 1b
   - `created` — today's date (YYYY-MM-DD)
   - `packages` — list of confirmed package names
   - `file_formats` — list of file extensions from the interview
   - `description` — one-sentence domain summary from the interview
3. Set `active: <slug>` so the new domain becomes immediately active.
4. If other domains already exist in the manifest, their entries are
   preserved — only `active` and the new domain entry change.

## Re-Run Safety

If invoked on a workspace that already has filled content:

- **Detect manifest** — Check `docs/domains/manifest.yaml`.  If it
  exists and has domains listed, ask: "Create a new domain or update
  the existing `<active-slug>` domain?"  If the user wants to update,
  suggest `/update-domain` instead.
- **Detect existing content** — Check whether markers already have
  links below them pointing to `docs/domains/`.
- **Check domain docs** — If domain doc files already exist for the
  target slug, audit their content before proposing changes.
- **Ask before overwriting** — If content exists, ask the user: "This
  section already has domain content.  Overwrite, skip, or append?"
- **Never silently overwrite** — User-edited content is precious.
  Default to skipping already-filled sections.
- **Legacy migration** — If `docs/domain/` (without the `s`) exists
  but no manifest, offer to migrate it first via the `/switch-domain`
  migration procedure before creating a new domain.

## What This Skill Does NOT Do

- Does **not** execute Python code or run analysis
- Does **not** install packages (suggest `pip install` commands instead)
- Does **not** require `sciagent[wizard]` — works with VS Code's
  built-in `fetch` and `editFiles` tools only
- Does **not** create new agent `.agent.md` files — it configures the
  existing template files and creates `docs/domains/<slug>/` knowledge
  files

## Domain Customization

<!-- Add domain-specific configuration notes below this line.
     Examples:
     - Default packages to always include for this domain
     - Preferred search queries for package discovery
     - Custom placeholder values to pre-fill
-->

---

## Incremental Update Mode

---
name: update-domain
description: Incrementally update domain knowledge — add new packages, refine workflows, or extend template content without re-running the full configuration interview. Use after initial /configure-domain setup.
argument-hint: What to update, e.g. "add scipy and statsmodels" or "update workflows for batch processing"
user-invokable: true
---

# Update Domain Knowledge

Incrementally update your SciAgent domain configuration.  Use this after
the initial `/configure-domain` setup to add new packages, refine
workflows, or extend template content without starting from scratch.

## When to Use

- You want to add a new package to your domain configuration.
- Your analysis workflows have changed and need updating.
- You discovered a new tool or library relevant to your research.
- You want to refine value ranges, parameters, or guardrails.
- You have new example data that reveals additional file formats or
  column patterns.

## Procedure

### Step 1 — Understand the Change

Ask the user what they want to update.  Common scenarios:

- **"Add package X"** — Discover, document, and integrate a new
  package into the template files.
- **"Update workflows"** — Modify or add workflow steps in
  `workflows.md`.
- **"Change parameters"** — Update analysis parameters, value ranges,
  or precision tables in `operations.md`.
- **"Add a custom skill"** — Create a new skill entry in `skills.md`.
- **"Full refresh"** — Re-audit all templates and fill any remaining
  placeholders (suggest `/configure-domain` instead if most content
  is missing).

### Step 2 — Audit Current State

Scan the relevant template files to understand what's already configured:

1. Search for files matching `*.instructions.md`, `operations.md`,
   `workflows.md`, `tools.md`, `library_api.md`, `skills.md`.
2. Identify which sections have domain content links vs. unfilled
   `<!replace ... --->` markers (or legacy `<!-- REPLACE: ... -->`
   placeholders).
3. Check `docs/domains/manifest.yaml` to identify the active domain
   and its directory (`docs/domains/<active-slug>/`).  If the
   manifest does not exist, fall back to checking `docs/domain/` for
   legacy single-domain setups.
4. Note any domain-specific content that might conflict with the
   proposed changes.
5. Brief the user: "Here’s your current configuration in the affected
   files (active domain: `<slug>`).  I'll update X and Y."

> **Tip:** To update a non-active domain, first run
> `/switch-domain <slug>` to make it active, then `/update-domain`.

### Step 3 — Discover (If Adding Packages)

If the user wants to add new packages:

1. Fetch PyPI metadata: `https://pypi.org/pypi/{name}/json`
2. If available, fetch the GitHub README for capabilities overview.
3. Present the package info and ask for confirmation.
4. If the user doesn't know the exact package name, use broader
   searches based on their description.

### Step 4 — Propose Edits

Before making changes, show the user exactly what will be modified:

- Which files will be edited
- What content will be added or changed
- Whether any existing content will be affected

Ask for confirmation before proceeding.

### Step 5 — Apply Updates

Use `editFiles` to make the confirmed changes.  Domain content should
live in `docs/domains/<active-slug>/` files, **not** inlined into the
template files:

- **Adding a package**: Update `docs/domains/<slug>/library-api.md`
  with API reference, `docs/domains/<slug>/tools.md` with tool
  documentation, and `docs/domains/<slug>/operations.md` if the
  package introduces new analysis parameters or workflows.  Also
  create `docs/domains/<slug>/skills/<package>/SKILL.md` with the
  per-package skill content and copy it into the workspace's active
  `skills/` directory.  If the template marker doesn't yet have a
  link below it, add one.
- **Updating workflows**: Edit the relevant section in
  `docs/domains/<slug>/workflows.md` (or
  `docs/domains/<slug>/operations.md` for the standard workflows
  section).
- **Changing parameters**: Edit the parameters section in
  `docs/domains/<slug>/operations.md`.
- **Adding skills**: Add a new skill section to
  `docs/domains/<slug>/skills.md` and optionally create a `SKILL.md`
  file in `docs/domains/<slug>/skills/<name>/` (and copy to
  the workspace's active `skills/` directory).

If `docs/domains/manifest.yaml` doesn't exist yet (e.g. the user ran
an older version of `/configure-domain`), create the directory and
manifest.  See `/switch-domain` for the manifest schema.

After applying changes, update the domain's entry in
`docs/domains/manifest.yaml` if packages or file formats changed.

### Step 6 — Verify

1. Confirm the edit was applied correctly by reading the modified file.
2. Summarize what was changed.
3. Note any follow-up actions (e.g. "You may want to run
   `/docs-ingestor` on the new package for a deeper API reference").

## Re-Run Safety

- **Preserve existing content** — Only modify the specific sections
  relevant to the update.  Do not touch unrelated template content.
- **Ask before overwriting** — If the target section already has
  different domain content, ask the user whether to replace, merge,
  or skip.
- **Append by default** — When adding new items (packages, workflows,
  skills), append to existing lists rather than replacing them.

## What This Skill Does NOT Do

- Does **not** execute Python code or run analysis
- Does **not** install packages (suggest `pip install` commands instead)
- Does **not** require `sciagent[wizard]`
- Does **not** replace the full `/configure-domain` flow for first-time
  setup — if most template content is missing, suggest running
  `/configure-domain` first

## Domain Customization

<!-- Add domain-specific update notes below this line.
     Examples:
     - Packages that should always be included when updating
     - Sections that should be checked on every update
     - Domain conventions for naming workflows or parameters
-->

---

## Domain Switching Mode

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
