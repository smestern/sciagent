# Tools Reference

This document describes the tools available in your agent. Tools are the
building blocks that agents use to perform analysis — each tool is a
function with defined inputs and outputs.

> **Tip:** Organise tools into logical categories (I/O, analysis, QC,
> fitting, etc.). Each tool should have a clear function signature,
> parameter table, and return schema so the LLM knows exactly how to
> call it and what to expect back.

## Tool Categories

<!-- REPLACE: tool_categories_toc — A bulleted list linking to each tool category section. Example:
- [I/O Tools](#io-tools) — File loading and data access
- [Analysis Tools](#analysis-tools) — Core domain analysis
- [QC Tools](#qc-tools) — Quality control
- [Fitting Tools](#fitting-tools) — Curve fitting and modelling
- [Visualisation Tools](#visualisation-tools) — Plotting and figure generation
-->

- [I/O Tools](#io-tools) — File loading and data access

---

<!-- REPEAT: tool_category — One section per tool category. Each category contains one or more tool subsections. -->

## <!-- REPLACE: tool_category_name — Category heading, e.g. "I/O Tools", "Analysis Tools", "QC Tools" -->

<!-- REPEAT: tool_section — One subsection per tool within this category. -->

### <!-- REPLACE: tool_name — The tool's function name, e.g. "load_file", "detect_events", "run_qc" -->

<!-- REPLACE: tool_short_description — A one-sentence description of what the tool does. Example: "Load a data file and return its contents as arrays." -->

```python
<!-- REPLACE: tool_signature — The full function signature with type hints. Example:
load_file(file_path: str, return_metadata: bool = False) -> Dict
-->
```

**Parameters**:

<!-- REPLACE: tool_parameters_table — A Markdown table of parameters. Columns: Name, Type, Default, Description. Example:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| file_path | str | required | Path to the data file |
| return_metadata | bool | False | Include file metadata in the response |
-->

| Name | Type | Default | Description |
|------|------|---------|-------------|
| *param* | *type* | *default* | *description* |

**Returns**:

```python
<!-- REPLACE: tool_returns — The return value structure as a Python dict literal. Example:
{
    "data": np.ndarray,        # The loaded data array
    "n_samples": int,          # Number of data points
    "metadata": dict           # File metadata (if requested)
}
-->
```

---

<!-- END_REPEAT -->

<!-- END_REPEAT -->

## Adding Custom Tools

To add a new tool:

1. Implement the tool function with clear type hints
2. Register it with the agent's tool loader
3. Document it in this file following the template above

### Tool Implementation Template

```python
from sciagent.tools.registry import tool

@tool(
    name="my_tool",
    description="Brief description of what the tool does",
    parameter_schema={
        "param1": {"type": "string", "description": "First parameter"},
        "param2": {"type": "number", "description": "Second parameter", "default": 1.0},
    },
)
async def my_tool(param1: str, param2: float = 1.0) -> str:
    \"\"\"Implement the tool logic here.\"\"\"
    # ... analysis code ...
    return result_as_string
```

### Best Practices

- Each tool should do **one thing well**
- Return structured data (dicts with clear keys) rather than free text
- Include units in return value descriptions
- Validate inputs before processing
- Handle errors gracefully and return informative messages
