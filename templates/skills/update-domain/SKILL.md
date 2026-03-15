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
