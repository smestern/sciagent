# Computational Neuroscience — Workflows

Domain-specific workflow definitions for biologically constrained computational modeling.

## Workflow Overview

| Workflow | Purpose | Key Steps |
|----------|---------|-----------|
| Model Building | Define and validate a biophysical neuron/network model | Define equations → set parameters → simulate → validate → iterate |
| Parameter Inference (SBI) | Estimate biophysical parameters from data | Define prior → build simulator → train estimator → condition on data → validate posterior |
| State Inference (SSM) | Infer latent states from neural time-series | Load data → preprocess → fit HMM/SLDS → select model → extract states → report |
| Parameter Sweep | Map parameter space to model behavior | Define grid → simulate → extract features → visualize landscape |
| Iterative Refinement | Progressively improve model fit to data | Baseline model → compare to data → identify mismatch → adjust → re-fit → validate |

---

## Model Building

**Purpose**: Define, simulate, and validate a biophysical neuron or network model in Brian2.

**When to Use**:
- Starting a new modeling project
- User asks to "build a model", "simulate a neuron", or "create a network"
- Testing a hypothesis about neural mechanisms

### Steps

1. **Define model equations** (use Brian2 `NeuronGroup`)
   - Specify differential equations for membrane potential, ion channels, synaptic currents
   - Include reset and threshold conditions for spiking
   - Verify equation dimensions with Brian2 unit system

2. **Set parameters**
   - Use biologically plausible parameter values (cite sources if known)
   - Organize parameters in a dictionary for reproducibility
   - Set random seed

3. **Run baseline simulation**
   - Use appropriate `dt` (default 0.1 ms, reduce if fast dynamics)
   - Simulate for sufficient duration to observe steady-state behavior
   - Record key state variables (`StateMonitor`) and spikes (`SpikeMonitor`)

4. **Validate**
   - Check for NaN/Inf in recorded variables
   - Verify resting potential is physiological (–80 to –60 mV)
   - Compare firing rate to expected range for the neuron type
   - Test `dt` sensitivity: re-run at half dt, compare results

5. **Report**
   - Model equations and parameters table
   - Voltage trace plot
   - Firing rate summary
   - Any validation warnings

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dt` | 0.1*ms | Integration time step |
| `duration` | 1*second | Simulation length |
| `method` | `'euler'` | Integration method (euler, rk2, rk4, exponential_euler) |
| `N` | 1 | Number of neurons (single-cell) or per-population (network) |

### Expected Outputs
- Brian2 `NeuronGroup` and `Network` objects
- `StateMonitor` traces (voltage, currents, gating variables)
- `SpikeMonitor` spike times
- Firing rate and basic statistics
- Parameter table

---

## Parameter Inference (SBI)

**Purpose**: Estimate biophysical model parameters by comparing simulations to experimental data using amortized Bayesian inference.

**When to Use**:
- User wants to "fit the model to data" or "estimate parameters"
- User asks about "posterior" or "parameter distributions"
- Matching a model to experimental recordings

### Steps

1. **Define prior distributions**
   - Use `sbi.utils.BoxUniform` or `torch.distributions` for each parameter
   - Bounds should be biologically plausible (e.g., g_Na: 1–200 nS)
   - Document the rationale for prior ranges

2. **Build simulator function**
   - `simulator(theta) → x` where theta is parameter vector, x is summary statistics
   - Summary statistics should capture the features of interest (firing rate, AP amplitude, ISI CV, etc.)
   - Ensure simulator is deterministic given a seed, or accounts for stochasticity

3. **Generate training data**
   - Sample parameters from prior
   - Run `N_simulations` (default 10,000) simulations
   - Extract summary statistics from each
   - Check for failed simulations (NaN, timeout) and exclude with logging

4. **Train neural posterior estimator**
   - Use `sbi.inference.SNPE` (default) or SNLE/SNRE
   - Train with default settings first, then tune if needed
   - Monitor training loss for convergence

5. **Condition on observed data**
   - Compute same summary statistics from experimental data
   - Sample from posterior: `posterior.sample((10000,), x=x_observed)`
   - Compute MAP estimate and credible intervals

6. **Validate posterior**
   - Posterior predictive check: simulate from posterior samples, compare to data
   - Simulation-based calibration (SBC) if time permits
   - Check for posterior concentration (not just prior echo)

7. **Report**
   - Prior vs posterior comparison plots
   - Parameter estimates with 95% credible intervals
   - Posterior predictive traces overlaid on data
   - Quality metrics (posterior z-scores, RMSE)

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `N_simulations` | 10000 | Number of training simulations |
| `density_estimator` | `'maf'` | Neural density estimator type |
| `num_rounds` | 1 | Number of sequential rounds (multi-round SNPE) |
| `n_posterior_samples` | 10000 | Samples from the posterior |

### Expected Outputs
- Trained posterior object
- Parameter estimates table with credible intervals
- Prior vs posterior corner plot
- Posterior predictive check figure
- Summary statistics comparison table

---

## State Inference (SSM)

**Purpose**: Fit a state-space model (HMM, SLDS) to neural time-series to infer latent discrete states and continuous dynamics.

**When to Use**:
- User has time-series data and asks to "find states" or "segment"
- User mentions "switching dynamics" or "regime changes"
- Analyzing transitions between behavioral or neural states

### Steps

1. **Load and inspect data**
   - Verify shape: `(T, N)` where T = time steps, N = observed dimensions
   - Check for NaN/Inf; report missing data fraction
   - Confirm sampling rate and units

2. **Preprocess**
   - Interpolate missing values: `ssm.preprocessing.interpolate_data(data, mask)`
   - Z-score or standardize if features have different scales
   - Construct mask array: `True` = observed, `False` = missing

3. **Fit model with multiple initializations**
   - Try K = 2, 3, 4, 5 states (or user-specified range)
   - For each K, run `N_init` fits (default 10) with different random seeds
   - Use Laplace-EM for SLDS or EM for HMM
   - Track ELBO for each fit

4. **Select best model**
   - Within each K: pick the fit with highest ELBO
   - Across K values: use held-out log-likelihood or information criteria
   - Report ELBO table and selection rationale

5. **Extract states and dynamics**
   - Most likely states: `model.most_likely_states(...)` (Viterbi)
   - Expected states: `model.expected_states(...)` (smoothed posterior)
   - For SLDS: extract dynamics matrices (A, B, Q) per state

6. **Validate**
   - Check state durations are reasonable (not too short)
   - Verify transitions make physical/biological sense
   - Compare reconstructed data to observed data

7. **Report**
   - State assignment over time
   - State-specific dynamics parameters
   - Transition matrix
   - ELBO comparison table
   - Reconstruction error

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `K` | 3 | Number of discrete states |
| `D` | 2 | Continuous latent dimensionality (SLDS) |
| `N_init` | 10 | Random initializations per model |
| `n_iters` | 200 | Max EM iterations |
| `method` | `'laplace_em'` | Fitting method for SLDS |
| `mask` | all True | Boolean mask for missing data |

### Expected Outputs
- Fitted SSM model object
- State sequence (most likely and posterior probabilities)
- Transition matrix
- Per-state dynamics parameters
- ELBO convergence plot
- State-colored time-series plot

---

## Parameter Sweep

**Purpose**: Systematically explore how model behavior changes across a parameter space.

**When to Use**:
- User asks about "bifurcations", "sensitivity", or "parameter space"
- Mapping out firing regimes of a neuron model
- Identifying which parameters have the largest effect on model output

### Steps

1. **Define parameter grid**
   - Select 1–3 parameters to vary
   - Define ranges and resolution (linear or log-spaced)
   - Keep all other parameters fixed at baseline values

2. **Run simulations**
   - Iterate over parameter combinations
   - For each: simulate, extract summary statistics
   - Handle failures gracefully (log, mark as NaN)

3. **Extract features**
   - Firing rate, spike count, ISI statistics
   - AP features (amplitude, half-width, threshold)
   - Or custom metrics relevant to the question

4. **Visualize**
   - 1D sweep: line plot (parameter vs. metric)
   - 2D sweep: heatmap or contour plot
   - Mark bifurcation boundaries

5. **Report**
   - Parameter ranges and resolution
   - Feature extraction methods
   - Heatmap/line figures
   - Key findings (e.g., "Tonic firing transitions to bursting at g_KCa > 50 nS")

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_points` | 20 | Points per parameter dimension |
| `spacing` | `'linear'` | Grid spacing (linear, log) |
| `n_repeats` | 1 | Repeats per point (for stochastic models) |

### Expected Outputs
- Parameter-metric data table
- Heatmap or line plot figures
- Identified regime boundaries
- Sensitivity ranking of parameters

---

## Iterative Refinement

**Purpose**: Progressively improve a computational model by comparing to experimental data and adjusting.

**When to Use**:
- User describes an iterative modeling process
- Model output doesn't match data well enough
- "The model fires too fast" or "the AP shape is wrong"

### Steps

1. **Establish baseline**
   - Run current model with current parameters
   - Extract summary statistics matching experimental measures
   - Quantify mismatch (RMSE, chi-squared, visual comparison)

2. **Identify mismatch source**
   - Which features disagree? (rate, shape, timing, variability)
   - Which parameters likely control those features?
   - Sensitivity analysis if unclear

3. **Adjust model**
   - Manual tuning: adjust 1–2 parameters at a time
   - Automated fitting: use SBI or optimization
   - Structural changes: add/remove ion channels, change morphology

4. **Re-evaluate**
   - Re-run simulation with adjusted parameters
   - Re-compute summary statistics
   - Compare improvement quantitatively

5. **Document iteration**
   - Log each iteration: parameters changed, rationale, result
   - Track improvement metrics across iterations
   - Report final model with full provenance

### Expected Outputs
- Iteration log table
- Before/after comparison figures
- Final parameter set with confidence
- Summary of what drove the improvement
