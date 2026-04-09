---
name: ssm
description: >
  Fit and analyze state-space models (HMM, SLDS, LDS) on neural time-series
  data using the ssm package. Handles missing data via masks, multiple
  initializations, model comparison, and latent state extraction.
argument-hint: Describe your state-space modeling goal, e.g. "fit SLDS to neural trajectories" or "HMM on behavioral states"
---

# SSM — State Space Models

## When to Use
- User wants to fit HMM, SLDS, or LDS models
- User mentions latent states, switching dynamics, or state segmentation
- Task involves time-series with discrete and/or continuous latent structure
- User needs model comparison across different numbers of states

## Key API

### Core Classes

#### `ssm.HMM(K, D, M=0, observations, transitions)`
- `K`: int — number of discrete states
- `D`: int — observation dimensionality
- `M`: int — input dimensionality (default 0)
- `observations`: str — emission model (`'gaussian'`, `'poisson'`, `'ar'`, `'diagonal_gaussian'`)
- `transitions`: str — transition model (`'standard'`, `'sticky'`, `'inputdriven'`)

**Key methods**:
- `.fit(datas, inputs=None, masks=None, method='em', num_iters=100)` → returns `log_probs`
- `.most_likely_states(data, input=None, mask=None)` → Viterbi decoding
- `.filter(data, input=None, mask=None)` → forward filtering
- `.smooth(data, input=None, mask=None)` → forward-backward smoothing
- `.log_likelihood(data, input=None, mask=None)` → scalar log-likelihood
- `.sample(T, input=None)` → sample from the generative model

#### `ssm.SLDS(N, K, D, M=0, emissions, dynamics, transitions)`
- `N`: int — observation dimensionality
- `K`: int — number of discrete states
- `D`: int — latent continuous dimensionality
- `M`: int — input dimensionality (default 0)
- `emissions`: str — emission model (`'gaussian'`, `'gaussian_orthog'`, `'poisson_orthog'`)
- `dynamics`: str — dynamics model (`'gaussian'`, `'diagonal_gaussian'`)
- `transitions`: str — transition model (`'standard'`, `'sticky'`, `'recurrent'`)

**Key methods**:
- `.fit(datas, inputs=None, masks=None, method='laplace_em', variational_posterior='structured_meanfield', num_iters=100, initialize=True)` → returns `(elbos, variational_posterior)`
- `.most_likely_states(variational_mean, data, input=None, mask=None)` → discrete state sequence
- `.smooth(variational_mean, data, input=None, mask=None)` → continuous latent trajectory

#### `ssm.LDS(N, D, M=0, emissions, dynamics)`
- Linear dynamical system (single continuous state, no switching)
- Same interface as SLDS but without `K`

### Preprocessing

#### `ssm.preprocessing.interpolate_data(data, mask)`
- Fills missing values via linear interpolation before fitting
- Use to initialize emission parameters when data has gaps

### Mask Format
- **Shape**: Same as data `(T, N)` for observations of shape `(T, N)`
- **dtype**: `bool`
- **Semantics**: `True` = observed (included in likelihood), `False` = missing (excluded)
- Masks are multiplied element-wise with log-likelihoods — masked entries contribute 0

## Common Pitfalls
1. **Data must be a list** — Even for single trial: `slds.fit([data])`, `hmm.fit([data])`
2. **Mask semantics** — `True` = observed, `False` = missing (opposite of some NaN conventions)
3. **SLDS initialization** — `initialize=True` runs PCA + AR-HMM init; set `False` if you provide custom init
4. **ELBO not log-likelihood** — SLDS `.fit()` returns ELBOs (lower bound), not exact log-likelihood
5. **Multiple initializations** — SLDS is non-convex; run 5–10 random inits and pick best final ELBO
6. **K selection** — Use held-out log-likelihood or cross-validation, not training ELBO, to choose K
7. **Numerical instability** — Large observation dimensions or many states can cause overflow; standardize data first
8. **variational_posterior** — Must use `'structured_meanfield'` for SLDS (not `'mf'`); the posterior object is needed for downstream calls

## Quick Recipes

### HMM on Neural Data
```python
import ssm
import numpy as np

K = 3       # number of states
D = 10      # observation dimensions
data = ...  # shape (T, D)

hmm = ssm.HMM(K, D, observations='gaussian')
log_probs = hmm.fit([data], method='em', num_iters=200)

states = hmm.most_likely_states(data)
smoothed = hmm.smooth(data)  # (T, K) state probabilities
```

### SLDS with Multiple Initializations
```python
import ssm
import numpy as np

N = 20   # observation dimensions
K = 3    # number of discrete states
D = 4    # latent continuous dimensions
data = ...  # shape (T, N)

best_elbo = -np.inf
best_model = None
for seed in range(10):
    np.random.seed(seed)
    slds = ssm.SLDS(N, K, D,
                     emissions='gaussian_orthog',
                     dynamics='diagonal_gaussian',
                     transitions='sticky')
    elbos, posterior = slds.fit(
        [data], method='laplace_em',
        variational_posterior='structured_meanfield',
        num_iters=200, initialize=True)
    if elbos[-1] > best_elbo:
        best_elbo = elbos[-1]
        best_model = slds
        best_posterior = posterior

states = best_model.most_likely_states(best_posterior.mean[0], data)
latents = best_posterior.mean[0]  # (T, D)
```

### Held-Out Cross-Validation with Masks
```python
import ssm
import numpy as np

data = ...  # shape (T, N)
mask_full = np.ones_like(data, dtype=bool)

# Hold out 20% of observations randomly
rng = np.random.default_rng(42)
test_idx = rng.random(data.shape) < 0.2
train_mask = mask_full.copy()
train_mask[test_idx] = False
test_mask = ~train_mask

# Interpolate missing training values for initialization
data_interp = ssm.preprocessing.interpolate_data(data, train_mask)

hmm = ssm.HMM(K=3, D=data.shape[1], observations='gaussian')
hmm.fit([data_interp], masks=[train_mask], method='em', num_iters=200)

# Evaluate on held-out entries
test_ll = hmm.log_likelihood(data, mask=test_mask)
```

## Validation Checklist
- [ ] Data passed as list of arrays `[data]` not bare array
- [ ] Mask shape matches data shape
- [ ] Multiple random initializations tried for SLDS
- [ ] ELBO is monotonically increasing (or nearly so) during fitting
- [ ] K selected via held-out data, not training metric
- [ ] Latent states are interpretable (not just fitting noise)
