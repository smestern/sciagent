# Example: Configure Domain

> **Skill:** `/configure-domain`
> **Domain:** <!-- Your domain here, e.g. "Calcium Imaging" -->

---

## Task

<!-- 1-2 sentences: what domain were you setting up? Example: -->
<!-- "Configure SciAgent for calcium imaging analysis of GCaMP6 recordings." -->

---

## Transcript

<!-- Paste the real conversation here. Annotate key moments with callout boxes like: -->

<!--
> **What's happening:** The skill asks targeted questions about your file formats,
> experimental paradigm, and typical analyses — it doesn't just ask "what's your
> domain?" and guess the rest.

> **What's happening:** Package discovery found `suite2p`, `CaImAn`, and
> `OASIS` — then fetched their PyPI metadata to verify they're maintained
> and compatible.

> **Why this matters:** A generic LLM might hallucinate package names or recommend
> abandoned libraries. The configure-domain skill verifies each package exists
> on PyPI and checks its maintenance status.
-->

---

## What Was Generated

<!-- Summarize or list the files/content that the skill produced. Example: -->

<!--
- `docs/domains/calcium-imaging/operations.md` — domain operations (ROI detection, dF/F, event detection)
- `docs/domains/calcium-imaging/workflows.md` — step-by-step analysis workflows
- `docs/domains/calcium-imaging/library-api.md` — API references for suite2p, CaImAn, OASIS
- `docs/domains/calcium-imaging/skills/` — 4 skill definitions (domain-expertise, suite2p, caiman, oasis)
- Updated `manifest.yaml` with new domain entry
-->

---

## Key Takeaway

<!-- What did SciAgent do here that setting up manually wouldn't?
     e.g., "Discovered `OASIS` for fast deconvolution — a package I wasn't aware of
     — and generated a complete SKILL.md with correct API usage patterns." -->

---

> **See also:** [Full configure-domain transcript](configure_domain_out.md) for an unabridged intracellular-ephys example.
