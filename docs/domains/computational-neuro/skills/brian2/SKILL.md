---
name: brian2
description: >
  Build, run, and analyze spiking neural network simulations using Brian2.
  Covers single-neuron models (HH, LIF, AdEx, Izhikevich), synaptic connections,
  network construction, parameter sweeps, and result analysis.
argument-hint: Describe your simulation goal, e.g. "HH neuron F-I curve" or "balanced E/I network"
---

# Brian2 — Spiking Neural Network Simulation

## When to Use
- User wants to build or run a neuron/network simulation
- User mentions Brian2, NeuronGroup, Synapses, or specific neuron models
- Task involves simulating membrane potential, spikes, or synaptic dynamics
- User wants parameter sweeps or bifurcation analysis on biophysical models

## Key API

### Core Classes

#### `NeuronGroup(N, model, threshold, reset, refractory, method, namespace, dt)`
- `N`: int — number of neurons
- `model`: str — differential equations as multi-line string
- `threshold`: str — spike condition (e.g. `'v > -20*mV'`)
- `reset`: str — post-spike reset (e.g. `'v = -65*mV'`)
- `refractory`: Quantity — refractory period (e.g. `2*ms`)
- `method`: str — integration method (`'euler'`, `'rk2'`, `'rk4'`, `'exponential_euler'`)

#### `Synapses(source, target, model, on_pre, on_post, method)`
- `source`, `target`: `NeuronGroup` — pre/post populations
- `model`: str — synaptic state equations
- `on_pre`: str — statements executed on presynaptic spike
- `on_post`: str — statements executed on postsynaptic spike (for STDP)
- Call `.connect(...)` after creation (e.g. `S.connect(p=0.1)`)

#### `StateMonitor(source, variables, record, dt)`
- Records continuous state variables (v, currents, etc.)
- `record`: bool or index array — which neurons to record

#### `SpikeMonitor(source)`
- Records spike times: `.t` (times), `.i` (neuron indices)
- `.count` — spike count per neuron

#### `Network(*objects)`
- Container for simulation objects
- `net.run(duration)` — advance simulation

### Units
Brian2 uses a unit system — **always** attach units:
```python
from brian2 import mV, ms, nA, uF, cm, msiemens, Hz, second
```

### Integration Methods
- `'exponential_euler'` — best for linear + exponential terms (AdEx)
- `'rk4'` — robust for HH-type models
- `'euler'` — fast but less accurate; use small dt

## Common Pitfalls
1. **Forgetting units** — `v = -65` will fail; must be `v = -65*mV`
2. **String equations** — Equations are multi-line strings, not Python expressions
3. **defaultclock.dt** — Must be set BEFORE creating NeuronGroup, not after
4. **Synapses.connect()** — Must be called explicitly; creation alone does nothing
5. **Refractory period** — Threshold is not checked during refractory; can mask bursting
6. **Namespace collisions** — Use `namespace={}` dict for external parameters
7. **StateMonitor indexing** — Access as `mon.v[0]` (neuron index), not `mon.v[:,0]`

## Quick Recipes

### HH Single Neuron
```python
from brian2 import *

eqs = '''
dv/dt = (g_Na*m**3*h*(E_Na-v) + g_K*n**4*(E_K-v) + g_L*(E_L-v) + I_ext) / C_m : volt
dm/dt = alpha_m*(1-m) - beta_m*m : 1
dn/dt = alpha_n*(1-n) - beta_n*n : 1
dh/dt = alpha_h*(1-h) - beta_h*h : 1
alpha_m = 0.1*(mV**-1) * (25*mV-v+VT) / (exp((25*mV-v+VT)/(10*mV)) - 1) / ms : Hz
beta_m = 4.0 * exp(-(v-VT+50*mV)/(18*mV)) / ms : Hz
alpha_n = 0.01*(mV**-1) * (10*mV-v+VT) / (exp((10*mV-v+VT)/(10*mV)) - 1) / ms : Hz
beta_n = 0.125 * exp(-(v-VT+60*mV)/(80*mV)) / ms : Hz
alpha_h = 0.07 * exp(-(v-VT+58*mV)/(20*mV)) / ms : Hz
beta_h = 1.0 / (exp((28*mV-v+VT)/(10*mV)) + 1) / ms : Hz
I_ext : amp/metre**2
'''

params = dict(
    g_Na=120*msiemens/cm**2, g_K=36*msiemens/cm**2, g_L=0.3*msiemens/cm**2,
    E_Na=50*mV, E_K=-77*mV, E_L=-54.4*mV, C_m=1*uF/cm**2, VT=-63*mV,
)

G = NeuronGroup(1, eqs, threshold='v > -20*mV', refractory=3*ms,
                method='rk4', namespace=params)
G.v = -65*mV
G.m = 0.05; G.h = 0.6; G.n = 0.32
G.I_ext = 10*uA/cm**2

mon = StateMonitor(G, 'v', record=True)
spk = SpikeMonitor(G)
run(500*ms)
```

### LIF Network (E/I balanced)
```python
from brian2 import *

N_e, N_i = 800, 200
eqs_lif = 'dv/dt = (E_L - v + R_m*I_ext) / tau_m : volt (unless refractory)'

E = NeuronGroup(N_e, eqs_lif, threshold='v > -50*mV', reset='v = -60*mV',
                refractory=2*ms, method='euler',
                namespace=dict(E_L=-60*mV, R_m=100*Mohm, tau_m=20*ms))
I = NeuronGroup(N_i, eqs_lif, threshold='v > -50*mV', reset='v = -60*mV',
                refractory=2*ms, method='euler',
                namespace=dict(E_L=-60*mV, R_m=100*Mohm, tau_m=10*ms))

S_ee = Synapses(E, E, on_pre='v += 0.5*mV'); S_ee.connect(p=0.02)
S_ei = Synapses(E, I, on_pre='v += 0.5*mV'); S_ei.connect(p=0.02)
S_ie = Synapses(I, E, on_pre='v -= 2.0*mV'); S_ie.connect(p=0.02)
S_ii = Synapses(I, I, on_pre='v -= 2.0*mV'); S_ii.connect(p=0.02)

E.v = 'E_L + randn()*5*mV'
I.v = 'E_L + randn()*5*mV'
E.I_ext = 0.5*nA; I.I_ext = 0.4*nA

spk_e = SpikeMonitor(E); spk_i = SpikeMonitor(I)
run(1*second)
```

## Validation Checklist
- [ ] Units attached to all quantities
- [ ] dt appropriate for model complexity (≤0.1 ms for HH)
- [ ] Resting potential matches expectation (±5 mV)
- [ ] Spike shape is physiological (amplitude, width)
- [ ] No NaN in state variables
- [ ] Network: E/I balance produces stable rates
