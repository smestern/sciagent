# Tools Reference

This document describes the tools available in your agent. Tools are the
building blocks that agents use to perform analysis — each tool is a
function with defined inputs and outputs.

> **Tip:** Organise tools into logical categories (I/O, analysis, QC,
> fitting, etc.). Each tool should have a clear function signature,
> parameter table, and return schema so the LLM knows exactly how to
> call it and what to expect back.

## Tool Categories

<!replace --- A bulleted list linking to each tool category section --- or add a link--->

- [I/O Tools](#io-tools) — File loading and data access
- [Documentation & Learning](#documentation--learning) — Library ingestion and doc lookup

---

## Documentation & Learning

Tools for ingesting library documentation and consulting ingested
references.  These let the agent learn unfamiliar libraries at runtime.

### `ingest_library_docs`

Deep-crawl documentation for a Python package and generate a structured
API reference document.  Crawls ReadTheDocs API pages, GitHub source code,
and PyPI metadata, then uses an LLM to extract classes, functions,
pitfalls, and recipes into a standard reference format.

The generated document is saved to the agent's docs directory and becomes
available via `read_doc(name)`.

> **Requires** `sciagent[wizard]` — install with `pip install sciagent[wizard]`.

```python
ingest_library_docs(package_name: str, github_url: str | None = None) -> Dict
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `package_name` | `str` | required | The PyPI package name (e.g. `"numpy"`, `"pandas"`, `"scikit-learn"`) |
| `github_url` | `str` | `None` | Optional GitHub repository URL for deeper source-code analysis. If omitted, discovered from PyPI metadata. |

**Returns**:

```python
{
    "status": "success",          # or "error"
    "doc_name": str,              # e.g. "scipy_api"
    "path": str,                  # Full path to the saved .md file
    "word_count": int,            # Word count of the generated reference
    "message": str,               # Human-readable confirmation
}
```

---

### `read_doc`

Read a previously ingested or manually placed documentation file from
the docs directory.

```python
read_doc(name: str) -> str
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | Document name without `.md` extension (e.g. `"scipy_api"`) |

**Returns**: The full Markdown content of the document, or an error
message if not found.

---

<!-- REPEAT: tool_category — One section per tool category. Each category contains one or more tool subsections. -->

## <!replace --- Category heading, e.g. "I/O Tools", "Analysis Tools", "QC Tools" --- or add a link--->

<!-- REPEAT: tool_section — One subsection per tool within this category. -->

### <!replace --- The tool's function name, e.g. "load_file", "detect_events", "run_qc" --- or add a link--->

<!replace --- A one-sentence description of what the tool does --- or add a link--->

```python
<!-- REPLACE: tool_signature — The full function signature with type hints. Example:
load_file(file_path: str, return_metadata: bool = False) -> Dict
-->
```

**Parameters**:

<!replace --- A Markdown table of parameters. Columns: Name, Type, Default, Description --- or add a link--->

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
