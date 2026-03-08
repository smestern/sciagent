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
2. In each file, look for `<!-- REPLACE: key — description -->` comments.
3. Build a checklist of every placeholder found, grouped by file.
4. Show the checklist to the user: "I found N unfilled placeholders
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

For each confirmed placeholder, generate domain-appropriate content and
use `editFiles` to replace the `<!-- REPLACE: key — description -->`
comment with the actual content.

**Fill order** (adjust based on which files have placeholders):

1. **operations.md** — Standard workflows, analysis parameters,
   parameter adjustment guidance, edge cases, reporting precision table
2. **workflows.md** — Workflow overview table, individual workflow
   sections with steps, parameters, and expected outputs
3. **library_api.md** — Core classes, key functions, common pitfalls,
   and quick-start recipes for confirmed packages
4. **tools.md** — Domain tool documentation and custom tool templates
5. **skills.md** — Domain-specific skill entries (if any custom skills
   are warranted by the domain)

For each placeholder, follow the examples provided in the comment's
description — each `<!-- REPLACE: key — description. Example: ... -->`
includes guidance on the expected format.

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

1. Re-scan all template files for remaining `<!-- REPLACE: ... -->`
   placeholders.
2. Summarize what was changed:
   - Files modified (with placeholder counts before/after)
   - Packages included
   - New sections added
3. If any placeholders remain unfilled (e.g. the user deferred some),
   note them and suggest running `/update-domain` later.

## Re-Run Safety

If invoked on a workspace that already has filled content:

- **Detect existing content** — Check whether placeholders have already
  been replaced with domain content.
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
  existing template files

## Domain Customization

<!-- Add domain-specific configuration notes below this line.
     Examples:
     - Default packages to always include for this domain
     - Preferred search queries for package discovery
     - Custom placeholder values to pre-fill
-->
