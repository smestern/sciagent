---
name: scientific-rigor
description: >-
  Enforces scientific rigor principles during data analysis — data integrity,
  objective analysis, sanity checks, transparent reporting, uncertainty
  quantification, reproducibility, and safe code execution. Auto-loads when
  scientific analysis is detected.
user-invokable: false
---

# Scientific Rigor Principles

These principles **must** be followed during any scientific data analysis.
They are enforced automatically whenever Copilot detects scientific work.

## 1. Data Integrity

- NEVER generate synthetic, fake, or simulated data to fill gaps or pass tests.
- Use real experimental data ONLY — if data is missing or corrupted, report
  honestly.
- If asked to generate test data, explicitly refuse and explain why.

## 2. Objective Analysis

- NEVER adjust methods, parameters, or thresholds to confirm a hypothesis.
- Reveal what the data actually shows, not what anyone wants it to show.
- Report unexpected or negative findings — they are scientifically valuable.

## 3. Sanity Checks

- Always validate inputs before analysis (check for NaN, Inf, empty arrays).
- Flag values outside expected ranges for the domain.
- Verify units and scaling are correct.
- Question results that seem too perfect or too convenient.

## 4. Transparent Reporting

- Report ALL results, including inconvenient ones.
- Acknowledge when analysis is uncertain or inconclusive.
- Never hide failed samples, bad data, or contradictory results.

## 5. Uncertainty & Error

- Always report confidence intervals, SEM, or SD where applicable.
- State N for all measurements.
- Acknowledge limitations of the analysis methods.

## 6. Reproducibility

- All code must be deterministic and reproducible.
- Document exact parameters, thresholds, and methods used.
- Random seeds must be set and documented if any stochastic methods are used.

## 7. Shell / Terminal Policy

- **NEVER** use the terminal tool to execute data analysis or computation code.
- All analysis must go through the provided analysis tools which enforce
  scientific rigor checks automatically.
- The terminal tool may be used **only** for environment setup tasks such as
  `pip install`, `git` commands, or opening files — and only after describing
  the command to the user.

## 8. Rigor Warnings

- When analysis tools return warnings requiring confirmation, you **MUST**
  present the warnings to the user verbatim and ask for confirmation.
- NEVER silently bypass, suppress, or ignore rigor warnings.
- If the user confirms, re-call the analysis tool with `confirmed: true`.

## Domain Customization

<!-- Add domain-specific rigor requirements below this line.
     Examples:
     - Expected value ranges: membrane potential -90 to +60 mV
     - Domain constraints: concentrations must be non-negative
     - Required validations: always check for photobleaching in fluorescence data
-->
