### Output Directory
Always save analysis outputs to a dedicated output directory rather than
the current working directory.  Use `output_dir = Path("./output")` as the
default and create it if it doesn't exist:

```python
from pathlib import Path

output_dir = Path("./output")
output_dir.mkdir(exist_ok=True)

# Save a figure
fig.savefig(output_dir / "plot.png", dpi=150, bbox_inches="tight")

# Save a CSV
import pandas as pd
df.to_csv(output_dir / "results.csv", index=False)

# Save any other output
(output_dir / "results.txt").write_text(summary)
```

Do NOT use `os.chdir()` — the process working directory must not change.
