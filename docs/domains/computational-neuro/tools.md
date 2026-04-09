# Computational Neuroscience — Tools

Domain-specific tool categories and documentation.

## Tool Categories

- [Simulation Tools](#simulation-tools) — Neuron and network model simulation
- [Inference Tools](#inference-tools) — State-space models and parameter estimation
- [Analysis Tools](#analysis-tools) — Feature extraction and comparison
- [I/O Tools](#io-tools) — Data loading and export

---

## Simulation Tools

### `build_brian2_model`

Define and compile a Brian2 neuron or network model from equations and parameters.

```python
build_brian2_model(
    equations: str,                # Brian2 equation string with units
    parameters: dict,              # parameter name → value mapping
    N: int = 1,                    # number of neurons
    threshold: str = 'v > -20*mV', # spike condition
    reset: str = 'v = -65*mV',    # post-spike reset
    method: str = 'euler',         # integration method
) -> brian2.NeuronGroup
```

**Returns**: Configured `NeuronGroup` ready for simulation.

### `run_simulation`

Execute a Brian2 simulation and return recorded data.

```python
run_simulation(
    network: brian2.Network,       # configured network
    duration: float,               # simulation time in ms
    dt: float = 0.1,               # time step in ms
    record_vars: list = ['v'],     # state variables to record
    seed: int = 42,                # random seed
) -> dict
```

**Returns**: Dict with keys `'traces'` (StateMonitor data), `'spikes'` (SpikeMonitor data), `'metadata'`.

### `parameter_sweep`

Run simulations across a parameter grid.

```python
parameter_sweep(
    model_fn: callable,            # function(params) → summary_stats
    param_ranges: dict,            # parameter name → (min, max, n_points)
    fixed_params: dict = {},       # parameters held constant
    n_workers: int = 1,            # parallel workers
) -> pd.DataFrame
```

**Returns**: DataFrame with parameter columns and summary statistic columns.

---

## Inference Tools

### `fit_hmm`

Fit a Hidden Markov Model to time-series data.

```python
fit_hmm(
    data: np.ndarray,              # shape (T, N)
    K: int = 3,                    # number of states
    observations: str = 'gaussian', # emission type
    mask: np.ndarray = None,       # boolean mask, True=observed
    n_init: int = 10,              # random initializations
    n_iters: int = 200,            # max EM iterations
) -> dict
```

**Returns**: Dict with `'model'`, `'states'`, `'elbos'`, `'transition_matrix'`.

### `fit_slds`

Fit a Switching Linear Dynamical System to time-series data.

```python
fit_slds(
    data: np.ndarray,              # shape (T, N)
    K: int = 3,                    # number of discrete states
    D: int = 2,                    # latent dimensionality
    mask: np.ndarray = None,       # boolean mask
    n_init: int = 10,              # random initializations
    n_iters: int = 200,            # max EM iterations
    method: str = 'laplace_em',    # fitting method
) -> dict
```

**Returns**: Dict with `'model'`, `'posterior'`, `'states'`, `'elbos'`, `'dynamics'`.

### `run_sbi`

Run simulation-based inference to estimate model parameters.

```python
run_sbi(
    simulator: callable,           # function(theta) → summary_stats
    prior: Distribution,          # torch prior distribution
    x_observed: torch.Tensor,     # observed summary statistics
    method: str = 'SNPE',         # inference method
    n_simulations: int = 10000,   # training simulations
    density_estimator: str = 'maf', # neural network type
) -> dict
```

**Returns**: Dict with `'posterior'`, `'samples'`, `'map_estimate'`, `'credible_intervals'`.

---

## Analysis Tools

### `extract_spike_features`

Extract features from simulated spike trains.

```python
extract_spike_features(
    voltage: np.ndarray,           # voltage trace (mV)
    time: np.ndarray,              # time array (ms)
    threshold: float = -20.0,      # spike detection threshold (mV)
) -> dict
```

**Returns**: Dict with `'spike_times'`, `'firing_rate'`, `'isi'`, `'cv_isi'`, `'ap_amplitudes'`, `'ap_halfwidths'`.

### `compare_models`

Compare fitted models using information criteria.

```python
compare_models(
    models: list,                  # list of fitted model dicts
    data: np.ndarray,             # observed data
    metric: str = 'elbo',         # comparison metric ('elbo', 'aic', 'bic')
) -> pd.DataFrame
```

**Returns**: DataFrame ranking models by the chosen metric.

### `posterior_predictive_check`

Generate simulations from posterior samples and compare to observed data.

```python
posterior_predictive_check(
    posterior_samples: torch.Tensor,  # shape (n_samples, n_params)
    simulator: callable,              # function(theta) → summary_stats
    x_observed: torch.Tensor,         # observed summary statistics
    n_checks: int = 100,              # number of posterior simulations
) -> dict
```

**Returns**: Dict with `'simulated_stats'`, `'p_values'`, `'coverage'`, `'figures'`.

---

## I/O Tools

### `load_nwb`

Load data from NWB files.

```python
load_nwb(
    filepath: str,                 # path to .nwb file
    data_key: str = None,          # specific data stream to load
) -> dict
```

**Returns**: Dict with `'data'`, `'metadata'`, `'timestamps'`, `'units'`.

### `load_morphology`

Load neuron morphology from SWC/ASC files.

```python
load_morphology(
    filepath: str,                 # path to .swc or .asc file
) -> dict
```

**Returns**: Dict with `'compartments'`, `'branches'`, `'total_length'`, `'surface_area'`.

### `export_results`

Export analysis results to CSV/HDF5.

```python
export_results(
    results: dict,                 # analysis results
    filepath: str,                 # output path
    format: str = 'csv',          # 'csv' or 'h5'
) -> str
```

**Returns**: Path to the exported file.
