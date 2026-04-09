# Computational Neuroscience (Biophysical Modeling)

Pre-configured domain setup for biologically constrained computational models of single neurons and networks.

## Scope

- **Techniques**: Biophysical neuron simulation (Hodgkin-Huxley, multi-compartment), spiking network models, state-space inference, simulation-based inference
- **Data formats**: NWB (.nwb), morphology files (.swc, .asc), parameter files (.json, .yaml), tabular/HDF5 (.csv, .h5)
- **Analyses**: Single-neuron simulation, network dynamics, HMM/SLDS inference, parameter fitting via SBI, parameter sweeps, sensitivity analysis, model comparison

## Packages

| Package | Purpose | Version |
|---------|---------|---------|
| [brian2](https://pypi.org/project/brian2/) | Spiking neural network simulator | ≥2.10 |
| [ssm](https://github.com/slinderman/ssm) | Bayesian state-space models (HMM, SLDS) | ≥0.0.1 (install from GitHub) |
| [sbi](https://pypi.org/project/sbi/) | Simulation-based inference (amortized posterior estimation) | ≥0.26 |

## Skills

| Skill | Directory | Description |
|-------|-----------|-------------|
| Domain Expertise | `skills/domain-expertise/` | Core terminology, methods, and domain knowledge |
| Brian2 | `skills/brian2/` | Neural simulator API reference and recipes |
| SSM | `skills/ssm/` | State-space models API reference |
| SBI | `skills/sbi/` | Simulation-based inference API reference |

## Example Analyses

- Build a Hodgkin-Huxley neuron model in Brian2 and match it to experimental F-I curves
- Fit an SLDS model to neural time-series data to infer latent dynamics
- Use SBI to estimate biophysical parameters from summary statistics of simulated traces
- Parameter sweep across conductance values to map firing regimes
- Compare model architectures using posterior predictive checks
