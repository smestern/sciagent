# Extracellular Electrophysiology

Pre-configured domain setup for multi-electrode extracellular recordings and spike sorting.

## Scope

- **Techniques**: Multi-electrode arrays (MEA), silicon probes, tetrodes, Neuropixels
- **Data formats**: NWB, Open Ephys, SpikeGLX, Plexon, Blackrock
- **Analyses**: Spike sorting, LFP analysis, population activity, cross-correlation, PSTHs, current source density

## Packages

| Package | Purpose | Version |
|---------|---------|---------|
| [neo](https://pypi.org/project/neo/) | Electrophysiology data I/O (multi-format) | ≥0.12 |
| [elephant](https://pypi.org/project/elephant/) | Electrophysiology analysis toolbox | ≥0.12 |
| [spikeinterface](https://pypi.org/project/spikeinterface/) | Unified spike sorting framework | ≥0.100 |
| [probeinterface](https://pypi.org/project/probeinterface/) | Probe geometry and channel mapping | ≥0.2 |

## Skills

| Skill | Directory | Description |
|-------|-----------|-------------|
| Domain Expertise | `skills/domain-expertise/` | Core terminology, methods, and domain knowledge |
| Elephant | `skills/elephant/` | Analysis toolbox API reference |
| Neo | `skills/neo/` | Data I/O API reference |
| probeinterface | `skills/probeinterface/` | Probe geometry API reference |
| SpikeInterface | `skills/spikeinterface/` | Spike sorting framework API reference |

## Example Analyses

- Spike sorting pipeline (preprocessing → sorting → curation → export)
- PSTH and raster plot construction
- Local field potential (LFP) spectral analysis
- Cross-correlation and functional connectivity
- Current source density (CSD) analysis
- Probe geometry visualization and channel mapping

## See Also

- [SpikeInterface documentation](https://spikeinterface.readthedocs.io/)
- [Neo documentation](https://neo.readthedocs.io/)
