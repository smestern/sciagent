# Intracellular Electrophysiology (Patch-Clamp)

Pre-configured domain setup for whole-cell and perforated patch-clamp recordings from individual neurons.

## Scope

- **Techniques**: Whole-cell current clamp, whole-cell voltage clamp, perforated patch
- **Data formats**: ABF (Axon Binary Format), NWB (Neurodata Without Borders), DAT
- **Analyses**: Action potential feature extraction, passive membrane properties (Rm, Cm, tau), F-I curves, dose-response relationships, synaptic events

## Packages

| Package | Purpose | Version |
|---------|---------|---------|
| [pyabf](https://pypi.org/project/pyabf/) | Read ABF files from Axon Instruments | ≥2.3 |
| [neo](https://pypi.org/project/neo/) | Electrophysiology data I/O (multi-format) | ≥0.12 |
| [elephant](https://pypi.org/project/elephant/) | Electrophysiology analysis toolbox | ≥0.12 |
| [eFEL](https://pypi.org/project/efel/) | Electrophysiology feature extraction | ≥5.0 |

## Skills

| Skill | Directory | Description |
|-------|-----------|-------------|
| Domain Expertise | `skills/domain-expertise/` | Core terminology, methods, and domain knowledge |
| eFEL | `skills/efel/` | Feature extraction API reference and recipes |
| Elephant | `skills/elephant/` | Analysis toolbox API reference |
| Neo | `skills/neo/` | Data I/O API reference |
| pyABF | `skills/pyabf/` | ABF file reader API reference |

## Example Analyses

- F-I curve construction from current-clamp recordings
- Passive property extraction (Rm, Cm, tau from exponential fits)
- Action potential waveform analysis (threshold, amplitude, half-width, AHP)
- Input resistance measurement from hyperpolarizing steps
- Rheobase determination

## See Also

- [PatchAgent](https://github.com/smestern/patchAgent) — full SciAgent implementation for this domain
- [Showcase: PatchAgent](../../showcase.md) — real-world walkthrough
