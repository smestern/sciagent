# Example: Configure Domain
>[!NOTE]
> **Skill:** `/configure-domain`  
> **Domain:** Biophysically Constrained Single Neuron Modeling and Network Modeling
>
>---
>
>## Task
>
>In this example, I tasked sciagent to self-assemble domain knowledge related to Single Neuron Modeling. However, I present an interesting problem, specifically we are building models that are constrained to intracellular and extracellular recordings from actual neurons. In this case the sciagent will have to find libraries related to (1) standard neural modelling software (2) intracellular and extracellular recording i/o. 
>
>
>## What Was Generated
>
>**Files Created (12 total)**
>
>Domain knowledge docs (under docs/domains/comp-neuro-models/):
>
>- operations.md — Standard workflows, analysis parameters, edge cases, reporting precision, domain guardrails
>- workflows.md — 5 detailed workflows: single-cell fitting, SBI posterior, state-space dynamics, batch comparison, FI analysis
>- library-api.md — API reference for Brian2, pyABF, SBI, SSM with core classes, key functions, pitfalls, and recipes
>- tools.md — Tool categories: I/O, model, optimization, error metrics, analysis
>- skills.md — Skill index for all 5 domain skills  
>
>
>Per-package SKILL.md files:
>
>- skills/domain-expertise/SKILL.md — Auto-loading domain context (value ranges, unit system, validation rules)
>- skills/brian2/SKILL.md — Brian2 model construction, simulation checklist, parameter sources
>- skills/pyabf/SKILL.md — ABF file loading patterns and conventions
>- skills/sbi/SKILL.md — SBI workflow (prior → simulate → train → sample → PPC)
>- skills/ssm/SKILL.md — HMM/SLDS fitting, masks, model selection, state interpretation  
>
>
>Registry:
>
>- manifest.yaml — Domain manifest with active domain, package list, file formats, skill paths
>
>---
>
>## Key Takeaway
>
>SciAgent fetched live PyPI metadata and GitHub READMEs for all four packages (Brian2, pyABF, SBI, SSM) and synthesized that information into **domain-specific reference docs** — not generic API stubs, but documentation shaped around the user's actual research context. For example, the generated [library-api.md](../domains/comp-neuro-models/library-api.md) doesn't just list class signatures; it includes pitfalls like SSM's mask semantics and Brian2's unit system gotchas, plus ready-made recipes for common workflows like SBI posterior predictive checks. Each package also got its own [SKILL.md](../../templates/skills/) with a structured checklist the agent follows at runtime — so when you later ask it to fit a state-space model, it already knows the correct SSM API patterns, mask conventions, and model-selection criteria without you re-explaining them. The entire 12-file domain configuration was produced from a single conversational prompt, turning a generic SciAgent installation into a specialized computational neuroscience assistant.
>
---

## Transcript

> **See also:** [Full configure-domain transcript](configure_domain_out.md) for an unabridged intracellular-ephys example.

<div style="text-align: right">  <b>User:</b>

/configure-domain In this workspace, we are working on biologically constrained single neuron models and network models. This workspace spans the field from model fitting to dynamics analysis. In particular, we will be working with the packages Brian2, pyABF, Sbi (mackelab), and SSM (Linderman lab)</div>

**Model:**

Here's my understanding of your domain. Please confirm so I can proceed:

**Research Domain**: Computational neuroscience — biologically constrained single neuron models and network models, spanning model fitting to dynamics analysis.

**Data Types & File Formats**: `.abf` (patch-clamp recordings), `.nwb` (Neurodata Without Borders), `.npy`/`.joblib` (model parameters, fitted results), `.csv` (feature tables)

**Packages**:
| Package | Role |
|---|---|
| **Brian2** | Spiking neuron simulation (adEx, cadEx, etc.) |
| **pyABF** | Load ABF patch-clamp recordings |
| **SBI** (mackelab `sbi`) | Simulation-based inference for posterior estimation |
| **SSM** (Linderman lab) | State-space models — HMM/SLDS for neural dynamics |

**Analysis Goals**: 
- Fit biophysical neuron models to whole-cell patch-clamp data
- Spike detection & AP feature extraction
- Optimizer-driven parameter search (Nevergrad, SBI, scikit-optimize, Ax)
- FI curve matching, spike-train error metrics (EMD, Wasserstein)
- State-space dynamics analysis (HMM/SLDS) on neural time series
- Network-level model construction and fitting

**Common Workflows**:
1. Load ABF/NWB → extract sweeps → detect spikes → extract features → fit model
2. Build Brian2 model → optimize parameters → evaluate spike-train errors
3. Fit SSM/SLDS to voltage traces → segment hidden states → analyze dynamics
4. Batch fit across cell recordings → compare parameters across conditions

**Value Ranges & Units**: Membrane potential -100 to +60 mV, currents -2000 to 2000 pA, conductance 0–500 nS, capacitance 5–350 pF, time constants 0.1–250 ms

**Suggested domain slug**: `comp-neuro-models`  
**Suggested display name**: "Computational Neuroscience — Biophysical Modeling & Dynamics"

Does this look right? Shall I proceed with this slug and display name, or would you prefer something different?


<div style="text-align: right">  <b>User:</b>

This looks great please proceed</div>

**Model:**

Great! Let me proceed with the full domain configuration. I'll start by discovering package info and then create all the domain knowledge files. 

Starting: *Discover packages via PyPI/GitHub* (4/9)



Fetched 4 resources

Package discovery complete. Here's what I found:

| Package | Version | Description | Source |
|---|---|---|---|
| **Brian2** | 2.10.1 | Clock-driven simulator for spiking neural networks | github.com/brian-team/brian2 |
| **pyABF** | 2.3.8 | Python interface to ABF electrophysiology files | github.com/swharden/pyABF |
| **SBI** | 0.25.0 | Simulation-based inference (mackelab) | github.com/sbi-dev/sbi |
| **SSM** | GitHub-only | State-space models (Linderman lab) — installed from GitHub | github.com/lindermanlab/ssm |

Now I'll create all domain knowledge files and update the templates. This involves creating ~10 files. 

Domain configuration is complete. Here's a summary of everything that was created:

**Domain**: `comp-neuro-models` — Computational Neuroscience: Biophysical Modeling & Dynamics

### Files Created (12 total)

**Domain knowledge docs** (under `docs/domains/comp-neuro-models/`):
- operations.md — Standard workflows, analysis parameters, edge cases, reporting precision, domain guardrails
- workflows.md — 5 detailed workflows: single-cell fitting, SBI posterior, state-space dynamics, batch comparison, FI analysis
- library-api.md — API reference for Brian2, pyABF, SBI, SSM with core classes, key functions, pitfalls, and recipes
- tools.md — Tool categories: I/O, model, optimization, error metrics, analysis
- skills.md — Skill index for all 5 domain skills

**Per-package SKILL.md files**:
- `skills/domain-expertise/SKILL.md` — Auto-loading domain context (value ranges, unit system, validation rules)
- `skills/brian2/SKILL.md` — Brian2 model construction, simulation checklist, parameter sources
- `skills/pyabf/SKILL.md` — ABF file loading patterns and conventions
- `skills/sbi/SKILL.md` — SBI workflow (prior → simulate → train → sample → PPC)
- `skills/ssm/SKILL.md` — HMM/SLDS fitting, masks, model selection, state interpretation

**Registry**:
- manifest.yaml — Domain manifest with active domain, package list, file formats, skill paths

**Template updated**:
- All ~33 `<!replace ...>` placeholders in sciagent-templates.md filled with domain content and links to the domain docs

Made changes.

---
