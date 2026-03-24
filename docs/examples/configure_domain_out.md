
# Example: `/configure-domain` Wizard Output

> **What is this?** This is a transcript of the `/configure-domain` skill running in VS Code Copilot Chat. The skill interviews you about your research domain, discovers relevant Python packages, and generates domain-specific skills and documentation.
>
> For more on domain configuration, see [Domain Examples](../domains/) or the [configure-domain skill](../../templates/skills/configure-domain/SKILL.md).

---

## Transcript

I'll start by gathering context on the workspace state — checking for existing domain configurations, scanning templates for placeholders, and reading the rigor instructions.    

Searched for files matching `**/docs/domains/manifest.yaml`, no matches

Searched for files matching `**/docs/domain/**`, no matches

Searched for regex `<!replace|<!-- REPLACE:` (`**/*.md`), 20 results

Read [](file:///c%3A/Users/SMest/.copilot/instructions/sciagent-rigor.instructions.md)

Good — no existing domain configuration. Let me read the template files with placeholders to understand the full scope.     

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/operations.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/workflows.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/library_api.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/tools.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/skills.md)

Now I have the full picture. You've described your domain as patch-clamp electrophysiology with a focus on intracellular ephys. Before proceeding, let me ask a few follow-up questions to fill in the details. 

Analyzing your answers...

Here's what I'll configure:

**Domain**: Intracellular Electrophysiology (Patch-Clamp)  
**Slug**: `intracellular-ephys`  
**Formats**: .abf, .nwb, .dat  
**Packages**: pyabf, neo, elephant, eFEL  
**Analysis**: AP features, passive properties, F-I curves, dose-response  
**Configurations**: Whole-cell CC, whole-cell VC, perforated patch  

**Placeholder audit** — I found unfilled `<!-- REPLACE: ... -->` markers in 5 template files:
- operations.md — 5 placeholders (workflows, parameters, edge cases, precision, parameter guidance)
- workflows.md — 8 placeholders (overview table + per-workflow sections)
- library_api.md — 7 placeholders (display name, URLs, TOC, classes, functions, pitfalls, recipes)
- tools.md — 7 placeholders (category TOC + per-tool sections)
- skills.md — 5 placeholders (per-skill sections)

I'll now fetch PyPI metadata for your confirmed packages, then create the domain docs and fill all placeholders. 



Fetched 4 resources

I have all the package metadata. Let me search for file creation tools before proceeding.I need to create new domain files. Let me create the directory structure and all domain knowledge files. 

Replacing 1 lines with 16 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/manifest.yaml)


```

```
Good, file creation works. Now I'll create all the domain knowledge files in parallel. 

Replacing 1 lines with 178 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/operations.md)

 

Replacing 1 lines with 291 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/workflows.md)

 

Replacing 1 lines with 385 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/library-api.md)

 

Replacing 1 lines with 189 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/tools.md)

 

Replacing 1 lines with 93 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills.md)


```

```

```

```

```

```

```

```

```

```
Domain docs created. Now I'll create the skill source-of-truth files under `docs/domains/intracellular-ephys/skills/`. 

Replacing 1 lines with 105 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/domain-expertise/SKILL.md)

 

Replacing 1 lines with 101 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/pyabf/SKILL.md)

 

Replacing 1 lines with 99 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/neo/SKILL.md)

 

Replacing 1 lines with 99 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/elephant/SKILL.md)

 

Replacing 1 lines with 134 lines in [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/efel/SKILL.md)


```

```

```

```

```

```

```

```

```

```
Compacted conversationAll 5 SKILL.md files created. Now I need to insert links below each `<!-- REPLACE: ... -->` marker in the template files. Let me read the template files to get exact placeholder text for precise edits.     

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/operations.md#1-1), lines 1 to 150

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/workflows.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/library_api.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/tools.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/skills.md)

Now let me read the rest of operations.md for remaining placeholders: 

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/operations.md#150-150), lines 150 to 250

Good. Now I have all the placeholder locations. Let me insert the links below each placeholder in all 5 templates. I'll use `multi_replace_string_in_file` for efficiency. 

Replacing 27 lines with 37 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/operations.md)


```

```
Now the workflows.md template: 

Replacing 4 lines with 8 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/workflows.md)


```

```
Now library_api.md:  

Replacing 5 lines with 15 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/library_api.md)


```

```
Now tools.md: 

Replacing 1 lines with 3 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/tools.md)


```

```
Now skills.md:  

Replacing 5 lines with 7 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills.md)


```

```
All template links inserted. Now let me copy the skill files into the workspace's active `skills/` directory and do the final verification scan.   

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/skills)

The active skills directory is skills. I need to create the domain-specific skills there. Let me read one existing skill to match the format:  

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/scientific-rigor/SKILL.md#1-1), lines 1 to 15

Good. Now I'll create the 5 skill directories in skills by copying from the domain docs: 

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/domain-expertise/SKILL.md#1-1), lines 1 to 10

Now let me create the skill files in the active skills directory. I'll read the full content of each domain skill file and create corresponding files in the active directory:       

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/domain-expertise/SKILL.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/pyabf/SKILL.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/neo/SKILL.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/elephant/SKILL.md)

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills/efel/SKILL.md)

Good, I have all the content. Now I'll create the skills in skills — these are the active workspace skills: 

Replacing 1 lines with 106 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/domain-expertise/SKILL.md)

 

Replacing 1 lines with 101 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/pyabf/SKILL.md)

 

Replacing 1 lines with 99 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/neo/SKILL.md)

 

Replacing 1 lines with 99 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/elephant/SKILL.md)

 

Replacing 1 lines with 134 lines in [](file:///c%3A/Users/SMest/source/sciagent/templates/skills/efel/SKILL.md)


```

```

```

```

```

```

```

```

```

```
All skills installed. Now let me do the final **verification scan** — check for any remaining unfilled placeholders to make sure everything is linked:  

Searched for text `<!-- REPLACE:` (`**/templates/*.md`), 20 results

The `<!-- REPLACE: ... -->` markers are still present in the template files — this is correct per the instructions (markers stay intact, links are inserted below them). Let me verify the links were properly inserted:       

Searched for text `docs/domains/intracellular-ephys` (`**/templates/*.md`), 14 results

All 14 domain links are in place across all 5 template files. Let me also verify the domain docs and skills directories are complete:     

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys)

Read [](file:///c%3A/Users/SMest/source/sciagent/docs/domains/intracellular-ephys/skills)

Read [](file:///c%3A/Users/SMest/source/sciagent/templates/skills)

Everything is in place. Here's the complete summary of the domain configuration:

---

## Configuration Complete: `intracellular-ephys`

### Files Created (12 new files)

**Domain knowledge docs** (intracellular-ephys):
- operations.md — standard workflows, analysis parameters, edge cases, reporting precision
- workflows.md — 7 step-by-step workflows (QC, AP features, passive properties, F-I curve, synaptic currents, dose-response, batch)
- library-api.md — API reference for pyabf, neo, elephant, eFEL with pitfalls and recipes
- tools.md — I/O, analysis, QC, and fitting tool signatures
- skills.md — skill registry entries

**Domain skill source-of-truth** (skills):
- `domain-expertise/SKILL.md`, `pyabf/SKILL.md`, `neo/SKILL.md`, `elephant/SKILL.md`, `efel/SKILL.md`

**Manifest**: manifest.yaml

### Active Skills Installed (5 new skills in skills)
- **domain-expertise** — value ranges, recording configs, protocols, guardrails
- **pyabf** — ABF file I/O, sweep access, metadata
- **neo** — unified ephys I/O, Block/Segment/AnalogSignal data model
- **elephant** — spike detection, ISI/CV/firing rate, signal processing
- **efel** — 250+ AP feature extraction, threshold config, critical pitfalls

### Template Links Inserted (14 links across 5 files)
- operations.md — 5 links
- workflows.md — 2 links
- library_api.md — 5 links
- tools.md — 1 link
- skills.md — 1 link

### Packages Configured
| Package | Version | Role |
|---------|---------|------|
| pyabf | 2.3.8 | ABF file reader |
| neo | 0.14.4 | Unified ephys I/O (ABF, NWB, HEKA) |
| elephant | 1.2.0 | Spike/ISI/firing rate analysis |
| eFEL | 5.7.20 | AP feature extraction (250+ features) |

### File Formats
`.abf` (Axon Binary), `.nwb` (Neurodata Without Borders), `.dat` (HEKA Patchmaster)

Made changes.