---
name: domain-expertise
description: >
  Computational neuroscience domain knowledge — biophysical parameter ranges,
  ion channel taxonomy, neuron type classification, modeling paradigms, and
  data interpretation guidelines. Auto-loads when the computational-neuro
  domain is active.
---

# Computational Neuroscience — Domain Expertise

## When to Use
- Interpreting simulation outputs (membrane potential, firing rates, synaptic currents)
- Validating biophysical parameter ranges
- Choosing appropriate model complexity for a given question
- Translating between experimental and simulation conventions

## Biophysical Parameter Reference

### Passive Membrane Properties

| Parameter | Symbol | Typical Range | Units | Notes |
|-----------|--------|---------------|-------|-------|
| Resting potential | V_rest | −80 to −60 | mV | Neuron-type dependent |
| Membrane capacitance | C_m | 0.5–2.0 | µF/cm² | ~1.0 for most neurons |
| Input resistance | R_in | 50–500 | MΩ | Higher in small neurons |
| Membrane time constant | τ_m | 10–50 | ms | τ = R_in × C_m |
| Axial resistivity | R_a | 100–300 | Ω·cm | For multi-compartment models |

### Ion Channel Conductances (Maximal)

| Channel | Symbol | Typical Range | Units | Notes |
|---------|--------|---------------|-------|-------|
| Fast Na⁺ | g_Na | 100–200 | mS/cm² | Spike initiation |
| Delayed-rectifier K⁺ | g_K | 20–40 | mS/cm² | Spike repolarization |
| Leak | g_L | 0.01–0.1 | mS/cm² | Sets R_in |
| Transient K⁺ (A-type) | g_A | 1–50 | mS/cm² | ISI regulation |
| Ca²⁺ (L-type) | g_CaL | 0.1–5 | mS/cm² | Plateau potentials |
| Ca²⁺ (T-type) | g_CaT | 0.1–2 | mS/cm² | Rebound bursting |
| Ca²⁺-activated K⁺ | g_KCa | 1–30 | mS/cm² | Spike-frequency adaptation |
| HCN (h-current) | g_h | 0.01–0.5 | mS/cm² | Sag, resonance |

### Reversal Potentials

| Ion | Symbol | Typical Value | Units |
|-----|--------|---------------|-------|
| Na⁺ | E_Na | +50 | mV |
| K⁺ | E_K | −90 to −80 | mV |
| Ca²⁺ | E_Ca | +120 to +140 | mV |
| Cl⁻ | E_Cl | −80 to −60 | mV |
| Leak | E_L | −70 to −60 | mV |

### Synaptic Parameters

| Parameter | AMPA | GABA_A | NMDA | Units |
|-----------|------|--------|------|-------|
| τ_rise | 0.2–0.5 | 0.5–1.0 | 2–5 | ms |
| τ_decay | 1–3 | 5–15 | 50–150 | ms |
| E_rev | 0 | −80 to −70 | 0 | mV |
| g_peak | 0.1–5 | 0.1–5 | 0.01–1 | nS |

## Neuron Type Classification

### Cortical
- **Pyramidal** — Regular spiking, spike-frequency adaptation, apical dendrite
- **Fast-spiking (PV+)** — Narrow spikes, high sustained rates, no adaptation
- **Low-threshold spiking (SOM+)** — Rebound bursting, adapting
- **VIP+** — Irregular spiking, disinhibitory

### Subcortical
- **Purkinje** — Complex dendritic arbor, complex spikes, tonic firing ~40 Hz
- **Medium spiny (MSN)** — Bistable, up/down states, low spontaneous rate
- **Dopaminergic (DA)** — Pacemaker ~4 Hz, burst/pause modes

## Modeling Paradigms

| Paradigm | Complexity | Use Case | Brian2 Approach |
|----------|-----------|----------|-----------------|
| LIF | Low | Network-scale, fast | `NeuronGroup` with threshold/reset |
| AdEx | Medium | Adaptation, bursting patterns | `NeuronGroup` with exponential term |
| Izhikevich | Medium | Diverse firing patterns | `NeuronGroup` with two ODE variables |
| HH | High | Biophysical channel dynamics | `NeuronGroup` with gating variables |
| Multi-compartment | Very high | Dendritic computation | Multiple `NeuronGroup` + axial coupling |

## Sanity Checks for Simulations

### Numerical Stability
- Membrane potential should stay between −100 and +60 mV (HH); flag NaN
- dt should be ≤ 0.1 ms for HH models; ≤ 0.5 ms for LIF
- Total simulation time should not exceed what is needed (minutes, not hours, for single-cell)
- Check that firing rates are physiologically plausible (0–500 Hz)

### Model Validation Checklist
1. Does the resting potential match expected value (within ±5 mV)?
2. Does the F-I curve show expected shape (monotonic for regular-spiking)?
3. Is the rheobase in a reasonable range for the neuron type?
4. Do spike shape features match: amplitude, half-width, AHP depth?
5. For network models: is E/I balance maintained? Population rate stable?

## Data Interpretation Guidelines

- **Simulation ≠ Experiment** — Simulations test model predictions, not biological truth
- **Parameter sensitivity** — If results change drastically with small parameter changes, the conclusion is fragile
- **Degeneracy** — Multiple parameter sets can produce similar behavior; report this
- **Mean-field vs single-trial** — Average over trials for rate estimates; single trials for variability
