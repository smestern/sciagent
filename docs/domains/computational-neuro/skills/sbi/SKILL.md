---
name: sbi
description: >
  Estimate biophysical model parameters using simulation-based inference (SBI).
  Covers prior definition, simulator wrapping, neural density estimation
  (SNPE, SNLE, SNRE), posterior analysis, and validation.
argument-hint: Describe your inference goal, e.g. "infer HH conductances from voltage trace" or "fit network params to firing rates"
---

# SBI — Simulation-Based Inference

## When to Use
- User wants to estimate model parameters from observed data without an explicit likelihood
- User mentions Bayesian inference, posterior, prior, or parameter fitting
- Task involves fitting a simulator (Brian2 or other) to experimental data
- User needs SNPE, SNLE, or SNRE

## Key API

### Prior Definition

#### `sbi.utils.BoxUniform(low, high)`
- `low`, `high`: `torch.Tensor` — bounds for each parameter dimension
- Returns a uniform distribution over a hyperrectangle
- For non-uniform priors, use any `torch.distributions.Distribution`

### Inference Classes

#### `sbi.inference.SNPE(prior, density_estimator='maf')`
- Sequential Neural Posterior Estimation
- `density_estimator`: str — `'maf'` (Masked Autoregressive Flow) or `'nsf'` (Neural Spline Flow)
- `.append_simulations(theta, x)` — add training data
- `.train()` → returns density estimator (neural network)
- `.build_posterior()` → returns `DirectPosterior`

#### `sbi.inference.SNLE(prior, density_estimator='maf')`
- Sequential Neural Likelihood Estimation
- Same interface as SNPE but estimates likelihood, not posterior directly
- Requires MCMC sampling from posterior

#### `sbi.inference.SNRE(prior, classifier='resnet')`
- Sequential Neural Ratio Estimation
- `classifier`: str — `'resnet'` or `'mlp'`
- Estimates likelihood-to-evidence ratio

### Posterior

#### `DirectPosterior`
- `.sample((n_samples,), x=x_observed)` → `torch.Tensor` of shape `(n_samples, n_params)`
- `.log_prob(theta, x=x_observed)` → log posterior density
- `.map(x=x_observed, num_init_samples=1000)` → MAP estimate

### Utilities

#### `sbi.utils.posterior_nn(model, hidden_features, num_transforms)`
- Configure the neural network architecture for the density estimator
- `model`: str — `'maf'`, `'nsf'`, `'mdn'`
- `hidden_features`: int — width of hidden layers (default 50)
- `num_transforms`: int — number of flow transforms (default 5)

#### `sbi.analysis.pairplot(samples, limits, labels, fig_size)`
- Pairwise marginal posterior plot (corner plot)
- `samples`: `torch.Tensor` or `np.ndarray` — posterior samples
- `limits`: list of [low, high] per dimension
- `labels`: list of str — parameter names

#### `sbi.utils.simulate_for_sbi(simulator, proposal, num_simulations)`
- Batch-simulate from proposal prior
- `simulator`: callable — `f(theta) -> x` (must accept and return tensors)
- Returns `(theta, x)` tensors

## Common Pitfalls
1. **Tensor types** — SBI uses PyTorch; convert numpy arrays with `torch.as_tensor(arr, dtype=torch.float32)`
2. **Simulator output** — Must return a 1-D tensor of summary statistics, not raw time series
3. **Summary statistics** — Choose informative summaries; poor summaries = poor posterior
4. **Prior range** — If prior is too wide, training is inefficient; if too narrow, true params may be excluded
5. **Simulation budget** — SNPE typically needs 10k–100k simulations; start with 10k and check convergence
6. **Sequential rounds** — Multi-round SNPE focuses simulations near the posterior; improves sample efficiency
7. **Posterior validation** — Always run posterior predictive checks and simulation-based calibration (SBC)
8. **GPU** — Move prior and inference to GPU for large simulation budgets: `device='cuda'`
9. **Reproducibility** — Set `torch.manual_seed(seed)` and `np.random.seed(seed)` before training

## Quick Recipes

### Basic SNPE Workflow
```python
import torch
import numpy as np
from sbi.inference import SNPE
from sbi.utils import BoxUniform, simulate_for_sbi

# Define prior over parameters
prior = BoxUniform(
    low=torch.tensor([0.0, 0.0, -80.0]),
    high=torch.tensor([200.0, 50.0, -50.0]),
)

# Define simulator: theta -> summary statistics
def simulator(theta):
    # theta is a 1-D tensor of parameters
    # Run your model (e.g., Brian2) and extract summary stats
    g_Na, g_K, E_L = theta.numpy()
    # ... run simulation ...
    summary = torch.tensor([firing_rate, mean_vm, spike_width], dtype=torch.float32)
    return summary

# Simulate training data
theta, x = simulate_for_sbi(simulator, prior, num_simulations=10_000)

# Train SNPE
inference = SNPE(prior, density_estimator='nsf')
inference.append_simulations(theta, x)
density_estimator = inference.train()
posterior = inference.build_posterior(density_estimator)

# Sample posterior given observed data
x_observed = torch.tensor([observed_rate, observed_vm, observed_width], dtype=torch.float32)
samples = posterior.sample((10_000,), x=x_observed)
```

### Posterior Predictive Check
```python
# Sample parameters from posterior
samples = posterior.sample((100,), x=x_observed)

# Simulate from each posterior sample
predictions = []
for theta in samples:
    x_pred = simulator(theta)
    predictions.append(x_pred.numpy())

predictions = np.stack(predictions)

# Compare prediction distribution to observed
for i, name in enumerate(stat_names):
    pred_mean = predictions[:, i].mean()
    pred_std = predictions[:, i].std()
    obs = x_observed[i].item()
    print(f"{name}: obs={obs:.3f}, pred={pred_mean:.3f} ± {pred_std:.3f}")
```

### Multi-Round Sequential SNPE
```python
from sbi.inference import SNPE
from sbi.utils import BoxUniform, simulate_for_sbi

prior = BoxUniform(low=torch.zeros(3), high=torch.ones(3))
inference = SNPE(prior)

proposal = prior
for round_idx in range(3):
    theta, x = simulate_for_sbi(simulator, proposal, num_simulations=5_000)
    inference.append_simulations(theta, x, proposal=proposal)
    density_estimator = inference.train()
    posterior = inference.build_posterior(density_estimator)
    proposal = posterior.set_default_x(x_observed)

# Final posterior is focused around x_observed
final_samples = posterior.sample((10_000,), x=x_observed)
```

## Validation Checklist
- [ ] Prior covers plausible biological parameter ranges
- [ ] Summary statistics are informative (test with known ground truth)
- [ ] Posterior predictive check shows observed data is within prediction range
- [ ] SBC rank histograms are uniform (if calibration is critical)
- [ ] MAP estimate produces simulation close to observed data
- [ ] Results reported with uncertainty (credible intervals, not point estimates)
