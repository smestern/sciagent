# Examples

Annotated transcripts showing SciAgent features in action. Each example is a real conversation excerpt with callout boxes explaining what the agent is doing and why it matters.

> **Want the full end-to-end story?** See [Showcase: PatchAgent](../showcase.md) for a complete walkthrough from data loading to publication-ready report.

---

## Feature Examples

| Example | Skill / Agent | What it shows |
|---------|---------------|---------------|
| [Analysis Planner](analysis-planner-example.md) | `/analysis-planner` | Step-by-step plan generation before any code runs |
| [Rigor Review](rigor-review-example.md) | `@sci-reviewer` | Agent catches statistical and reproducibility issues |
| [Configure Domain](configure-domain-example.md) | `/configure-domain` | First-time domain setup interview + package discovery |
| [Data QC](data-qc-example.md) | `/data-qc` | Systematic quality control report on a messy dataset |

## Full Transcripts

| Example | Description |
|---------|-------------|
| [Configure Domain (full transcript)](configure_domain_out.md) | Unabridged wizard output from an intracellular-ephys setup |

---

## Adding Your Own

If you have a compelling example of SciAgent in your domain, we'd love to include it. Format:

1. **Task** — 1-2 sentences describing what the user asked
2. **Agent/Skill** — which agent or `/skill` was invoked
3. **Transcript** — annotated conversation with `> **Note:**` callout boxes
4. **Key takeaway** — what SciAgent did that a generic LLM wouldn't

Submit a PR or open an issue with your transcript.
