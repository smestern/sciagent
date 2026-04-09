# Computational Neuroscience — Library API Reference

Domain library references for brian2, ssm, and sbi.

---

## Brian2 API Reference

> **Source**: https://github.com/brian-team/brian2
> **Docs**: https://brian2.readthedocs.io/
> **Purpose**: Simulator for spiking neural networks — define models with
> differential equations, simulate dynamics, record variables and spikes.

### Table of Contents

1. [Core Classes](#brian2-core-classes)
2. [Key Functions](#brian2-key-functions)
3. [Common Pitfalls](#brian2-common-pitfalls)
4. [Quick-Start Recipes](#brian2-quick-start-recipes)

### Brian2 Core Classes

#### `NeuronGroup`

Create a group of neurons with specified dynamics.

```python
from brian2 import NeuronGroup, ms, mV, nS
```

##### Constructor

```python
NeuronGroup(
    N,                  # int — number of neurons
    model,              # str or Equations — differential equations
    method='euler',     # str — integration method ('euler', 'rk2', 'rk4', 'exponential_euler')
    threshold='v > -20*mV',  # str — spike condition
    reset='v = -65*mV',     # str — post-spike reset
    refractory=2*ms,        # Quantity — refractory period
    dt=0.1*ms,              # Quantity — time step (overrides defaultclock)
    namespace=None,          # dict — variable namespace for equations
)
```

> ⚠️ Equations must be dimensionally consistent — Brian2 enforces unit checking.

##### Key Attributes
- `.v` — membrane potential array
- `.I` — injected current (if defined in model)
- `.N` — number of neurons

#### `Synapses`

Connect neuron groups with synaptic models.

```python
from brian2 import Synapses
```

```python
Synapses(
    source,        # NeuronGroup — presynaptic group
    target,        # NeuronGroup — postsynaptic group (can be same as source)
    model='',      # str — synaptic equations (state variables)
    on_pre='',     # str — action on presynaptic spike
    on_post='',    # str — action on postsynaptic spike (for STDP)
    method='euler',
    dt=None,
)
```

##### Connection Methods
- `.connect(condition='i!=j')` — all-to-all except self
- `.connect(p=0.1)` — random with probability
- `.connect(i=[0,1], j=[2,3])` — explicit connections

#### `StateMonitor`

Record state variables over time.

```python
from brian2 import StateMonitor

mon = StateMonitor(group, 'v', record=True)  # record all neurons
mon = StateMonitor(group, ['v', 'I'], record=[0, 5])  # specific neurons
```

##### Key Attributes
- `.t` — time array (with units)
- `.v` — recorded variable array, shape `(n_recorded, n_timesteps)`
- `mon[0].v` — voltage trace for neuron 0

#### `SpikeMonitor`

Record spike times.

```python
from brian2 import SpikeMonitor

spk = SpikeMonitor(group)
```

##### Key Attributes
- `.t` — all spike times (sorted)
- `.i` — neuron indices for each spike
- `.count` — spike count per neuron
- `.spike_trains()` — dict mapping neuron index → spike time array

#### `Network`

Container for simulation objects.

```python
from brian2 import Network

net = Network(neurons, synapses, mon, spk)
net.run(1*second, report='text')
```

### Brian2 Key Functions

#### `run(duration, report=None)`

Run the default network.

```python
from brian2 import run, second
run(1*second)
```

#### `TimedArray(values, dt)`

Create a time-varying input signal.

```python
from brian2 import TimedArray, ms
stimulus = TimedArray(current_trace, dt=0.1*ms)
# Use in equations: 'I = stimulus(t) : amp'
```

#### `defaultclock.dt`

Set global time step.

```python
from brian2 import defaultclock, us
defaultclock.dt = 50*us
```

### Brian2 Common Pitfalls

1. **Unit errors**: Brian2 enforces dimensional analysis. `v = -65` fails; use `v = -65*mV`.
2. **Forgetting `store()`/`restore()`**: To re-run a simulation from the same initial state, use `net.store()` before and `net.restore()` after.
3. **Code generation mode**: By default Brian2 uses C++ standalone or Cython. If falling back to Python (RuntimeMode), simulations are 10–100× slower. Check with `brian2.prefs.codegen.target`.
4. **`record=True` memory**: Recording all variables for large groups over long durations can exhaust memory. Record only needed neurons.
5. **Refractory period type**: Refractory period must have time units. `refractory=2` silently fails; use `refractory=2*ms`.
6. **Equation string formatting**: Multi-line equation strings must use `:` for unit declarations. E.g., `'dv/dt = (I - v) / tau : volt'`.

---

## SSM API Reference

> **Source**: https://github.com/slinderman/ssm
> **Docs**: See GitHub README and examples
> **Purpose**: Bayesian learning and inference for state-space models:
> HMM, LDS, SLDS, and variants.

### Table of Contents

1. [Core Classes](#ssm-core-classes)
2. [Key Functions](#ssm-key-functions)
3. [Common Pitfalls](#ssm-common-pitfalls)
4. [Quick-Start Recipes](#ssm-quick-start-recipes)

### SSM Core Classes

#### `HMM`

Hidden Markov Model with discrete latent states and configurable emissions.

```python
import ssm

hmm = ssm.HMM(
    K,                          # int — number of discrete states
    D,                          # int — observation dimensionality
    observations='gaussian',    # str — emission type ('gaussian', 'poisson', 'bernoulli', 'ar', etc.)
    transitions='standard',     # str — transition type ('standard', 'sticky', 'inputdriven')
)
```

##### Key Methods
- `.fit(datas, inputs=None, masks=None, method='em', num_iters=100)` → returns ELBOs list
- `.log_likelihood(data, inputs=None, masks=None)` → float
- `.most_likely_states(data, input=None, mask=None)` → `np.ndarray` of state indices
- `.expected_states(data, input=None, mask=None)` → tuple of (expected_states, expected_joints)
- `.sample(T, input=None)` → tuple of (states, observations)
- `.initialize(datas, inputs=None, masks=None)` → initialize parameters from data

#### `SLDS`

Switching Linear Dynamical System — discrete switching + continuous linear dynamics.

```python
slds = ssm.SLDS(
    N,                          # int — observation dimensionality
    K,                          # int — number of discrete states
    D,                          # int — continuous latent dimensionality
    emissions='gaussian',       # str — emission type
    dynamics='gaussian',        # str — dynamics type
    transitions='standard',     # str — transition type
)
```

##### Key Methods
- `.fit(datas, inputs=None, masks=None, method='laplace_em', variational_posterior='structured_meanfield', num_iters=200, initialize=True)` → returns (elbos, posterior)
- `.most_likely_states(variational_mean, data, input=None, mask=None)` → state sequence
- `.expected_states(variational_mean, data, input=None, mask=None)` → state posterior
- `.smooth(variational_mean, data, input=None, mask=None)` → smoothed continuous states
- `.sample(T, input=None)` → tuple of (states, continuous_states, observations)
- `.log_likelihood(data, inputs=None, masks=None)` → float (approximate)

##### Key Attributes
- `.dynamics.As` — dynamics matrices, shape `(K, D, D)`
- `.dynamics.bs` — dynamics biases, shape `(K, D)`
- `.dynamics.Sigmas` — dynamics noise covariances
- `.transitions.log_Ps` — log transition matrix
- `.emissions.Cs` — emission matrices (continuous → observed)
- `.emissions.ds` — emission biases

#### `LDS`

Linear Dynamical System (no switching).

```python
lds = ssm.LDS(
    N,                          # int — observation dimensionality
    D,                          # int — latent dimensionality
    emissions='gaussian',
    dynamics='gaussian',
)
```

### SSM Key Functions

#### `ssm.preprocessing.interpolate_data(data, mask)`

Fill missing values via linear interpolation. Useful before fitting to initialize emission parameters.

```python
data_filled = ssm.preprocessing.interpolate_data(data, mask)
```

### SSM Common Pitfalls

1. **Mask semantics**: `True` = observed, `False` = missing. This is the opposite of some other libraries (e.g., NumPy masked arrays where `True` = masked out).
2. **Data shape**: Data must be `(T, N)` — time × features. Not `(N, T)`.
3. **Multiple datasets**: `fit()` accepts a **list** of arrays: `[data1, data2, ...]`. Each can have different T but must have the same N.
4. **SLDS fitting returns a tuple**: `elbos, posterior = slds.fit(...)`. Don't forget to capture the posterior object — you need it for `most_likely_states()`.
5. **Random initialization sensitivity**: SLDS fits are sensitive to initialization. Always run multiple fits (≥10) and pick the best ELBO.
6. **Laplace-EM convergence**: Watch the ELBO sequence. If it fluctuates wildly, try reducing the learning rate or switching to a different variational posterior.
7. **Install from GitHub**: The PyPI version (0.0.1) is outdated. Install from source: `pip install git+https://github.com/slinderman/ssm.git`.

---

## SBI API Reference

> **Source**: https://github.com/sbi-dev/sbi
> **Docs**: https://sbi-dev.github.io/sbi/
> **Purpose**: Simulation-based inference — estimate posterior distributions
> over simulator parameters using neural density estimation.

### Table of Contents

1. [Core Classes](#sbi-core-classes)
2. [Key Functions](#sbi-key-functions)
3. [Common Pitfalls](#sbi-common-pitfalls)
4. [Quick-Start Recipes](#sbi-quick-start-recipes)

### SBI Core Classes

#### `SNPE` (Sequential Neural Posterior Estimation)

The most common inference method — directly estimates the posterior.

```python
from sbi.inference import SNPE

inference = SNPE(
    prior=prior,                    # torch.distributions.Distribution
    density_estimator='maf',        # str — 'maf', 'nsf', 'mdn', or custom
    device='cpu',                   # str — 'cpu' or 'cuda'
)
```

##### Key Methods
- `.append_simulations(theta, x)` — add training data (parameters, summary stats)
- `.train(training_batch_size=50, learning_rate=5e-4, show_train_summary=True)` → density_estimator
- `.build_posterior(density_estimator)` → `DirectPosterior`

#### `SNLE` (Sequential Neural Likelihood Estimation)

Estimates the likelihood instead of the posterior.

```python
from sbi.inference import SNLE
inference = SNLE(prior=prior, density_estimator='maf')
```

#### `SNRE` (Sequential Neural Ratio Estimation)

Estimates the likelihood-to-evidence ratio.

```python
from sbi.inference import SNRE
inference = SNRE(prior=prior, classifier='resnet')
```

#### `DirectPosterior`

The posterior object returned by `build_posterior()`.

```python
posterior = inference.build_posterior(density_estimator)
```

##### Key Methods
- `.sample((n_samples,), x=x_observed)` → `torch.Tensor` of shape `(n_samples, n_params)`
- `.log_prob(theta, x=x_observed)` → log probability of parameters
- `.map(x=x_observed, num_init_samples=1000)` → MAP estimate

### SBI Key Functions

#### `sbi.utils.BoxUniform`

Uniform prior over a box (hyperrectangle).

```python
from sbi.utils import BoxUniform
import torch

prior = BoxUniform(
    low=torch.tensor([1.0, 0.1]),     # lower bounds
    high=torch.tensor([200.0, 50.0]), # upper bounds
)
```

#### `sbi.utils.posterior_nn`

Build a custom neural network for the posterior.

```python
from sbi.utils import posterior_nn

density_estimator = posterior_nn(
    model='maf',              # 'maf', 'nsf', 'mdn'
    hidden_features=50,
    num_transforms=5,
)
```

#### `sbi.analysis.pairplot`

Plot pairwise marginals of posterior samples.

```python
from sbi.analysis import pairplot

fig, axes = pairplot(
    samples,              # torch.Tensor or np.ndarray (n_samples, n_params)
    limits=[[0, 200], [0, 50]],
    labels=['g_Na', 'g_K'],
    figsize=(8, 8),
)
```

#### `sbi.utils.simulation_utils.simulate_for_sbi`

Utility to run simulations in parallel.

```python
from sbi.utils import simulate_for_sbi

theta, x = simulate_for_sbi(
    simulator,        # callable: theta → x
    prior,
    num_simulations=10000,
    num_workers=4,
)
```

### SBI Common Pitfalls

1. **Tensor types**: SBI expects `torch.Tensor` inputs. Convert numpy arrays: `torch.tensor(data, dtype=torch.float32)`.
2. **Simulator must return fixed-size output**: The summary statistics vector must always have the same length, even if the simulation fails. Handle failures by returning a vector of NaN or zeros with appropriate logging.
3. **Prior and posterior device mismatch**: Ensure prior, data, and density estimator are on the same device (CPU or GPU).
4. **Not enough simulations**: For >5 parameters, 10k simulations may not suffice. Start with 10k for prototyping, scale to 50k–100k for final results.
5. **Summary statistics choice**: Poor summary statistics → poor posterior. Include statistics that are sensitive to the parameters you want to infer. Test informativeness by checking if different parameter values produce different summary statistics.
6. **Multi-round SNPE**: When using multiple rounds, the proposal prior shifts. Be careful with the `num_rounds` parameter and monitor for prior-posterior mismatch warnings.
7. **Posterior predictive checks are essential**: Always simulate from posterior samples and compare to observed data. A good training loss does not guarantee a good posterior.

---

## Quick-Start Recipes

### Brian2: Hodgkin-Huxley Neuron

```python
from brian2 import *

# Parameters
area = 20000*umetre**2
Cm = 1*ufarad*cm**-2 * area
gl = 5e-5*siemens*cm**-2 * area
El = -65*mV
EK = -90*mV
ENa = 50*mV
g_na = 100*msiemens*cm**-2 * area
g_kd = 30*msiemens*cm**-2 * area
VT = -63*mV

eqs = '''
dv/dt = (gl*(El-v) - g_na*(m*m*m)*h*(v-ENa) - g_kd*(n*n*n*n)*(v-EK) + I) / Cm : volt
dm/dt = 0.32*(mV**-1)*4*mV/exprel((13.*mV-v+VT)/(4.*mV))/ms*(1-m)-0.28*(mV**-1)*5*mV/exprel((v-VT-40.*mV)/(5.*mV))/ms*m : 1
dn/dt = 0.032*(mV**-1)*5*mV/exprel((15.*mV-v+VT)/(5.*mV))/ms*(1.-n)-.5*exp((10.*mV-v+VT)/(40.*mV))/ms*n : 1
dh/dt = 0.128*exp((17.*mV-v+VT)/(18.*mV))/ms*(1.-h)-4./(1+exp((40.*mV-v+VT)/(5.*mV)))/ms*h : 1
I : amp
'''

G = NeuronGroup(1, eqs, threshold='v > -20*mV', refractory=3*ms, method='exponential_euler')
G.v = El
G.I = 0.7*nA  # injected current

M = StateMonitor(G, 'v', record=0)
S = SpikeMonitor(G)

run(500*ms)
```

### SSM: Fit SLDS to Neural Data

```python
import ssm
import numpy as np

np.random.seed(42)

# data shape: (T, N_observed)
K, D, N = 3, 2, 10  # 3 states, 2 latent dims, 10 observed dims

slds = ssm.SLDS(N, K, D, emissions='gaussian', dynamics='gaussian')

# Fit with multiple initializations
best_elbo = -np.inf
best_model = None
for init in range(10):
    model = ssm.SLDS(N, K, D, emissions='gaussian', dynamics='gaussian')
    elbos, posterior = model.fit(data, method='laplace_em', num_iters=200)
    if elbos[-1] > best_elbo:
        best_elbo = elbos[-1]
        best_model = model
        best_posterior = posterior

states = best_model.most_likely_states(best_posterior.mean, data)
```

### SBI: Parameter Inference for a Neuron Model

```python
import torch
from sbi.inference import SNPE
from sbi.utils import BoxUniform

# Define prior over 2 parameters (g_Na, g_K in nS)
prior = BoxUniform(low=torch.tensor([10.0, 5.0]), high=torch.tensor([200.0, 80.0]))

# Simulator: parameters → summary statistics
def simulator(theta):
    g_na, g_k = theta.numpy()
    # ... run Brian2 model with these conductances ...
    # ... extract summary stats (firing rate, AP amplitude, etc.)
    return torch.tensor([firing_rate, ap_amplitude, isi_cv], dtype=torch.float32)

# Train
inference = SNPE(prior=prior)
theta, x = simulate_for_sbi(simulator, prior, num_simulations=10000)
density_estimator = inference.append_simulations(theta, x).train()
posterior = inference.build_posterior(density_estimator)

# Infer
x_observed = torch.tensor([15.0, 80.0, 0.3])  # from experiment
samples = posterior.sample((10000,), x=x_observed)
```
