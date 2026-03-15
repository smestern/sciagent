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
