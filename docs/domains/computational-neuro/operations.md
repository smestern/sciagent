# Computational Neuroscience — Operations

Domain-specific operations content for biologically constrained computational modeling.

## Standard Workflows

### Workflow A: Model Definition & Validation
```
1. Define neuron/network model (equations, parameters, topology)
2. Run baseline simulation with known-good parameters
3. Validate against analytical solutions or published benchmarks
4. Check numerical stability (dt sensitivity, no divergence)
5. Report model summary (N neurons, N synapses, duration, dt)
```

### Workflow B: Parameter Fitting (SBI)
```
1. Define prior distributions over parameters of interest
2. Build simulator function (parameters → summary statistics)
3. Generate training simulations (prior predictive samples)
4. Train neural posterior estimator (SNPE/SNLE/SNRE)
5. Condition on observed data to get posterior
6. Validate posterior (posterior predictive checks, coverage)
7. Report parameter estimates with credible intervals
```

### Workflow C: State Inference (SSM/SLDS)
```
1. Load observed time-series data
2. Preprocess: interpolate missing values, z-score if needed
3. Fit HMM/SLDS with multiple random initializations
4. Select best model by ELBO or held-out log-likelihood
5. Extract most likely states (Viterbi) and posterior means
6. Validate: check state durations, transition structure
7. Report latent states, dynamics matrices, and diagnostics
```

### Workflow D: Parameter Sweep / Sensitivity Analysis
```
1. Define parameter grid or sampling scheme
2. Run simulations across parameter space
3. Extract summary statistics per simulation
4. Build parameter-to-output mapping (heat maps, surfaces)
5. Identify bifurcation boundaries and sensitive parameters
6. Report with parameter landscape visualizations
```

### Workflow E: Model Comparison
```
1. Define competing model architectures
2. Fit each model to the same dataset
3. Compare using information criteria (ELBO, WAIC, log-likelihood)
4. Perform posterior predictive checks for each model
5. Report comparison table with model rankings
```

## Analysis Parameters

| Parameter | Default | Context |
|-----------|---------|---------|
| `dt` | 0.1 ms | Brian2 simulation time step |
| `duration` | 1000 ms | Default simulation duration |
| `N_init` | 10 | Number of random initializations (SSM fitting) |
| `N_simulations` | 10000 | Training simulations for SBI |
| `n_states` (K) | 2–5 | Number of discrete states for HMM/SLDS |
| `latent_dim` (D) | 2–4 | Continuous latent dimensionality for SLDS |
| `seed` | 42 | Default random seed for reproducibility |

### When to Adjust Parameters

**Smaller `dt` (0.01–0.05 ms)**:
- Fast-spiking neurons (Kv3+ channels)
- Synaptic integration at short time scales
- Numerical instability at larger dt

**Larger `dt` (0.5–1.0 ms)**:
- Rate-based network models
- Long simulations (>10 s) where speed matters
- Slow dynamics only (no fast spikes)

**More N_simulations (50k–100k)**:
- High-dimensional parameter spaces (>5 params)
- Multimodal posteriors
- Complex summary statistics

**Fewer N_simulations (1k–5k)**:
- Low-dimensional problems (2–3 params)
- Fast iteration during model development
- Preliminary exploration

## Edge Cases

**Simulation divergence (NaN/Inf)**:
- Reduce `dt` by factor of 2–5
- Check for missing `clip` or `reset` conditions
- Verify ion channel kinetics are bounded
- Report the time point of divergence

**SBI posterior collapse (all mass on prior boundary)**:
- Check summary statistics are informative
- Verify simulator produces variable outputs
- Try different neural network architecture
- Consider sequential methods (multi-round SNPE)

**SLDS fit instability (ELBO oscillating or decreasing)**:
- Increase number of random initializations
- Try different emission models (Gaussian vs Poisson)
- Reduce latent dimensionality
- Check for data scaling issues

**Numerical precision in log-likelihoods**:
- Use log-space computations throughout
- Watch for underflow in long time-series
- Verify mask handling for missing data

## Reporting Precision

| Measurement | Precision | Units |
|-------------|-----------|-------|
| Membrane potential | 1 decimal | mV |
| Conductance | 2 significant figures | nS or µS/cm² |
| Time constants | 1 decimal | ms |
| Firing rate | 1 decimal | Hz |
| Current | 1 decimal | pA or nA |
| Capacitance | 1 decimal | pF or µF/cm² |
| ELBO / log-likelihood | 2 decimals | nats |
| Posterior mean | 3 significant figures | (parameter units) |
| Credible interval | 2 significant figures | (parameter units) |
| Transition probability | 3 decimals | — |
| Latent state duration | 1 decimal | ms or s |

## Domain Guardrails

### Forbidden Patterns
- **NEVER** compare models trained on different subsets of data without accounting for data differences
- **NEVER** select number of states (K) based solely on best ELBO without cross-validation or held-out evaluation
- **NEVER** report SBI posteriors without posterior predictive checks
- **NEVER** use unstable simulations (containing NaN/Inf) as training data for SBI
- **NEVER** average parameter posteriors across subjects without hierarchical modeling
- **NEVER** ignore simulation `dt` sensitivity — always verify key results at 2× finer resolution

### Warning Patterns
- ⚠️ Brian2 simulations running slower than expected → check for Python-mode fallback (should use C++ code generation)
- ⚠️ SLDS states with very short durations (<5 time steps) → possible over-fitting, consider fewer states
- ⚠️ SBI posterior much narrower than prior → verify not overfitting to noise; check with simulated data
- ⚠️ Parameter at prior boundary → prior may be misspecified; consider widening
