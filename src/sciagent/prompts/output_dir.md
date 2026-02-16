### Output Directory (OUTPUT_DIR)
The execution environment exposes an `OUTPUT_DIR` variable (a `pathlib.Path`)
pointing to the agent's output directory.  **Always save files there** instead
of to the current working directory:

```python
# Save a figure
fig.savefig(OUTPUT_DIR / "plot.png", dpi=150, bbox_inches="tight")

# Save a CSV
import pandas as pd
df.to_csv(OUTPUT_DIR / "results.csv", index=False)

# Save any other output
(OUTPUT_DIR / "results.txt").write_text(summary)
```

Do NOT use `os.chdir()` — the process working directory must not change.
Every script you execute is automatically saved to `OUTPUT_DIR/scripts/`
for reproducibility.
