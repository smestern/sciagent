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

### Step 2 — Audit Templates

Scan the workspace for SciAgent instruction files and identify unfilled
placeholders:

1. Search for files matching `*.instructions.md`, `operations.md`,
   `workflows.md`, `tools.md`, `library_api.md`, `skills.md` in
   `.github/instructions/` and the workspace root.
2. In each file, look for `<!replace ... --->` markers (or legacy
   `<!-- REPLACE: key — description -->` comments).
3. Also check whether `docs/domain/` already exists with domain
   knowledge files from a previous run.
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

**Domain docs structure** — create one file per template in `docs/domain/`:

- `docs/domain/operations.md` — Standard workflows, analysis parameters,
  parameter adjustment guidance, edge cases, reporting precision table
- `docs/domain/workflows.md` — Workflow overview table, individual
  workflow sections with steps, parameters, and expected outputs
- `docs/domain/library-api.md` — Core classes, key functions, common
  pitfalls, and quick-start recipes for confirmed packages
- `docs/domain/tools.md` — Domain tool documentation and custom tool
  templates
- `docs/domain/skills.md` — Domain-specific skill entries (if any
  custom skills are warranted by the domain)

**For each placeholder:**

1. Read the marker description to understand the expected content —
   each `<!replace --- description --- or add a link--->` (or legacy
   `<!-- REPLACE: key — description. Example: ... -->`) includes
   guidance on the expected format.
2. Write the domain-appropriate content under a Markdown heading in the
   corresponding `docs/domain/<template>.md` file.  Use headings that
   match the placeholder description (e.g. `## Standard Workflows`,
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

See [domain workflows](docs/domain/operations.md#standard-workflows)
```

The full workflow content lives in `docs/domain/operations.md` under a
`## Standard Workflows` heading.

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
3. Write a condensed reference to the `docs/` directory following the
   `library_api.md` format (Core Classes, Key Functions, Common
   Pitfalls, Quick-Start Recipes)

For deeper documentation crawling, suggest the user invoke
`/docs-ingestor` (requires `sciagent[wizard]`).

### Step 7 — Verify

1. Re-scan all template files for remaining `<!replace ...>` markers
   without links below them.
2. Verify that `docs/domain/` files were created with the expected
   content.
3. Summarize what was changed:
   - Files modified (with placeholder counts before/after)
   - Domain docs created
   - Packages included
   - New sections added
4. If any placeholders remain unfilled (e.g. the user deferred some),
   note them and suggest running `/update-domain` later.

## Re-Run Safety

If invoked on a workspace that already has filled content:

- **Detect existing content** — Check whether markers already have
  links below them pointing to `docs/domain/`.
- **Check domain docs** — If `docs/domain/*.md` files already exist,
  audit their content before proposing changes.
- **Ask before overwriting** — If content exists, ask the user: "This
  section already has domain content.  Overwrite, skip, or append?"
- **Never silently overwrite** — User-edited content is precious.
  Default to skipping already-filled sections.

## What This Skill Does NOT Do

- Does **not** execute Python code or run analysis
- Does **not** install packages (suggest `pip install` commands instead)
- Does **not** require `sciagent[wizard]` — works with VS Code's
  built-in `fetch` and `editFiles` tools only
- Does **not** create new agent `.agent.md` files — it configures the
  existing template files and creates `docs/domain/` knowledge files

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
3. Check `docs/domain/` for existing domain knowledge files from a
   previous `/configure-domain` run.
4. Note any domain-specific content that might conflict with the
   proposed changes.
5. Brief the user: "Here's your current configuration in the affected
   files.  I'll update X and Y."

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
live in `docs/domain/` files, **not** inlined into the template files:

- **Adding a package**: Update `docs/domain/library-api.md` with API
  reference, `docs/domain/tools.md` with tool documentation, and
  `docs/domain/operations.md` if the package introduces new analysis
  parameters or workflows.  If the template marker doesn't yet have a
  link below it, add one.
- **Updating workflows**: Edit the relevant section in
  `docs/domain/workflows.md` (or `docs/domain/operations.md` for the
  standard workflows section).
- **Changing parameters**: Edit the parameters section in
  `docs/domain/operations.md`.
- **Adding skills**: Add a new skill section to `docs/domain/skills.md`
  and optionally create a `SKILL.md` file in `.github/skills/`.

If `docs/domain/` doesn't exist yet (e.g. the user ran an older version
of `/configure-domain`), create the directory and the appropriate domain
knowledge file.

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
