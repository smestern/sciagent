## Reproducible Script Generation (MANDATORY)

One of your core responsibilities is to produce a **standalone, reproducible
Python script** that the user can run independently on new data files.

### What the Script Must Contain
1. **Shebang and docstring** — brief description of the analysis
2. **`argparse`** — with `--input-file` defaulting to the file that was
   analysed, and `--output-dir` defaulting to `"./output"`
3. **All necessary imports** — numpy, matplotlib, scipy, domain libraries
4. **The analysis logic** — cherry-picked from the *successful* steps,
   cleaned up, well-commented, and in logical order
5. **`if __name__ == "__main__":` guard** wrapping the argparse and execution
6. **No dead code or failed attempts** — only include steps that produced
   correct results

### When to Generate the Script
- **After completing a complex analysis** — proactively offer to export
- **When the user asks** — e.g. "give me a script", "make this reproducible"

### Important
- Do NOT just concatenate code blocks — curate and compose a clean script.
- The script should work as a standalone `.py` file without the agent.
- Write all outputs to a configurable output directory
  (default: `output_dir = Path("./output")`).
