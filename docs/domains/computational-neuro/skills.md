# Computational Neuroscience — Skills

Domain-specific skill definitions for biophysical modeling workflows.

---

## Brian2 Simulation

**File**: `skills/brian2/SKILL.md`

**Purpose**: Build, run, and analyze spiking neural network simulations using Brian2.

**Key Capabilities**:
- Define single-neuron models (HH, LIF, AdEx, Izhikevich) with proper Brian2 units
- Build network models with synaptic connections (AMPA, GABA, NMDA, STDP)
- Run simulations with appropriate dt and record state variables
- Extract firing statistics (rate, ISI, CV, F-I curves)
- Parameter sweeps and bifurcation analysis
- Validate numerical stability (dt sensitivity, NaN checks)

**Trigger Keywords**: brian2, simulate, neuron model, spiking, network, HH, Hodgkin-Huxley, LIF, conductance, synapse, NeuronGroup, firing rate

---

## State-Space Model Inference

**File**: `skills/ssm/SKILL.md`

**Purpose**: Fit and analyze state-space models (HMM, SLDS, LDS) on neural time-series data.

**Key Capabilities**:
- Fit HMM with configurable emissions (Gaussian, Poisson, AR)
- Fit SLDS with Laplace-EM and structured mean-field posterior
- Handle missing data via boolean masks
- Multiple random initializations with best-ELBO selection
- Extract latent states, dynamics matrices, transition probabilities
- Model comparison across different K (number of states)
- Cross-validation with held-out data masks

**Trigger Keywords**: ssm, state space, HMM, hidden Markov, SLDS, switching, latent states, dynamics, transitions, ELBO, segmentation

---

## Simulation-Based Inference

**File**: `skills/sbi/SKILL.md`

**Purpose**: Estimate model parameters using amortized Bayesian inference with neural density estimation.

**Key Capabilities**:
- Define priors over biophysical parameters (BoxUniform, custom distributions)
- Build simulator wrappers (Brian2 → summary statistics)
- Train SNPE, SNLE, or SNRE estimators
- Multi-round sequential inference
- Posterior sampling and MAP estimation
- Posterior predictive checks and simulation-based calibration
- Pairplot and corner plot visualization

**Trigger Keywords**: sbi, inference, posterior, prior, Bayesian, parameter estimation, SNPE, fit to data, likelihood-free, amortized

---

## Domain Expertise

**File**: `skills/domain-expertise/SKILL.md`

**Purpose**: Provide domain context for computational neuroscience — terminology, biophysical parameter ranges, and modeling conventions.

**Key Capabilities**:
- Biophysical parameter reference (conductances, capacitances, reversal potentials)
- Ion channel taxonomy (Na, K, Ca, leak, HCN, etc.)
- Neuron type classification (pyramidal, interneuron, Purkinje, etc.)
- Standard modeling paradigms (single-compartment, multi-compartment, mean-field)
- Data interpretation guidelines for simulated vs experimental data

**Trigger Keywords**: domain, neuroscience, biophysical, ion channel, conductance, membrane, neuron type, modeling convention
