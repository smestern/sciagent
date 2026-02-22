# Showcase: PatchAgent

A real-world walkthrough of SciAgent applied to **patch-clamp electrophysiology** — demonstrating how a domain-specific agent handles rudimentary analysis, nuanced computation, and reproducible script generation.

> See [PatchAgent on GitHub](https://github.com/smestern/patchAgent) for the full implementation.

---

## The Problem

The current wave of AI-for-science tools focuses on two things: literature search and end-to-end experimental pipelines. But most life science researchers don't need AI to run end-to-end research for them. They need help **writing strong, rigorous research code** — and default agentic AI falls flat in two specific ways:

1. **Hallucinations / Fakery** — AI often writes scripts that analyze "idealized data" or makes up data to pass tests. Sometimes it will [p-hack](https://en.wikipedia.org/wiki/Data_dredging) for the researcher.
2. **Domain knowledge gaps** — Researchers use jargon and domain-specific tools that models haven't memorized. Specialized libraries are often invoked incorrectly.

SciAgent addresses both problems:
- **Rigour reinforcements** that remind the AI not to fabricate data and to double- and triple-check its work.
- **Domain-specific tools** with documented APIs and expert knowledge baked into the system prompt.

---

## Background: Patch-Clamp Electrophysiology

[Patch-clamp electrophysiology](https://en.wikipedia.org/wiki/Patch_clamp) is a technique that allows neuroscientists to record signals from individual neurons with high precision. The recordings are **highly patterned time series** with features like [action potentials (spikes)](https://en.wikipedia.org/wiki/Action_potential) — the primary mechanism of signal propagation within a neuron.

PatchAgent is a full SciAgent implementation for this domain, demonstrating:
- Custom ABF/NWB file loaders
- Domain-specific tools (spike detection, passive properties, QC)
- Physiological bounds checking
- A specialized system prompt with neuroscience expertise

---

## Part 1: Rudimentary Analysis — F-I Curves

**Task:** Detect action potentials from neurons across three experimental conditions and analyze the F-I curve (Frequency vs. Injection current).

The dataset uses the proprietary [ABF format](https://swharden.com/pyabf/abf2-file-format/). General coding agents fail to reliably invoke the `pyabf` library — but PatchAgent has it documented.

### Challenges in this dataset

1. Several outliers that should be caught and removed
2. A unique stimulus structure (uncommon in the field) that must be accommodated
3. The dataset is not publicly available — the agent has no prior knowledge of it

### Results

The first-pass analysis works well:
- The agent correctly identifies the stimulus period
- It selects appropriate files to exclude (outliers)
- It plots all F-I curves correctly
- It correctly reasons that the +condition dampens the overall firing rate, while +condition+rescue restores it to control levels

---

## Part 2: Nuanced Analysis — Membrane Capacitance

**Task:** Compute membrane capacitance — a proxy for neuronal size.

Neuronal membranes act as capacitors. Neuroscientists model neurons as simplified RC circuits, where:

$$
\tau = RC
$$

The model must:
1. Fit an exponential to the sub-threshold voltage component to extract the time constant $\tau$
2. Compute membrane resistance $R_m$
3. Derive capacitance: $C_m = \tau / R_m$

### Results

The agent:
- Correctly computes capacitance using the RC circuit model
- Properly removes two outliers from the control condition (known outliers the researcher expected the agent to catch)
- Produces clean plots comparing passive properties across conditions

---

## Part 3: Reproducible Script Generation

**Task:** Generate a standalone analysis script that can be applied to other datasets.

SciAgent's core philosophy is that agents should produce **reproducible research code** — not just answers. The generated script (~150 lines) includes:

- Configurable parameters (protocol timing, QC thresholds, condition patterns)
- Proper dataclasses for structured data storage
- dV/dt-based spike detection via `ipfx` (scientifically appropriate)
- Exponential curve fitting for passive properties
- Statistical comparisons (ANOVA + Bonferroni post-hoc)
- Comprehensive docstrings and CLI interface

```python
#!/usr/bin/env python3
"""
Comprehensive Electrophysiology Analysis Script
================================================
Analyzes: F-I curves, passive membrane properties, active properties,
AP waveform features, and statistical comparisons.

Usage:
    python ephys_analysis.py --input-dir <path> --output-dir <path>
"""
# ... full script with configurable parameters, data classes,
# spike detection, curve fitting, and statistical analysis
```

The script is immediately runnable on new datasets with minimal configuration changes.

---

## What This Demonstrates

| SciAgent Feature | How PatchAgent uses it |
|------------------|----------------------|
| Domain tools | Custom ABF loader, spike detector, passive property calculator |
| Bounds checker | Physiological ranges (capacitance 5-500 pF, resistance > 0 MΩ) |
| Code scanner | Blocks synthetic data generation, enforces real data loading |
| System prompt | Neuroscience expertise, electrophysiology terminology |
| Reproducible scripts | Standalone Python scripts with CLI, docs, and configurable parameters |

---

## Try It Yourself

```bash
# Clone PatchAgent
git clone https://github.com/smestern/patchAgent.git
cd patchAgent

# Install
pip install -e ".[all]"

# Run
python -m patch_agent          # CLI
python -m patch_agent --web    # Web UI
```

Or use it as a reference to build your own sciagent for your research domain — see [Getting Started: Fullstack](getting-started-fullstack.md).

---

## Further Reading

- [PatchAgent Repository](https://github.com/smestern/patchAgent)
- [Getting Started: Fullstack](getting-started-fullstack.md) — build your own agent
- [API / Programmatic Usage](api-usage.md) — the `BaseScientificAgent` API PatchAgent is built on
- [Architecture](architecture.md) — how the guardrails pipeline works
