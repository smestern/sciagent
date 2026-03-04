---
name: docs-ingestor
description: Ingest documentation for any Python library — crawls PyPI, ReadTheDocs, and GitHub to produce a structured API reference (classes, functions, pitfalls, recipes). Use when the agent needs to learn an unfamiliar library for scientific analysis. Requires sciagent[wizard].
argument-hint: Python package name, e.g. scipy, neo, pyabf
user-invokable: true
---

# Library Documentation Ingestor

Ingest and learn the API of any Python library so you can use it
correctly in scientific analysis code.

## When to Use

- The user asks you to work with a library you don't have detailed
  knowledge of (e.g. a niche scientific package).
- You need to know the exact constructor signatures, method names,
  parameter defaults, or return types for a library.
- You want to avoid hallucinating API details — ingest first, then code.
- The user explicitly asks you to "learn" or "look up" a library.

## Procedure

### Step 1 — Check for Existing Docs

Before ingesting, check whether a reference already exists:

```
read_doc("<package>_api")
```

If a doc is returned, skip to Step 4.

### Step 2 — Ingest the Library

Call the ingestion tool with the PyPI package name:

```
ingest_library_docs(package_name="<package>")
```

Optionally provide a `github_url` for deeper source-code crawling:

```
ingest_library_docs(package_name="<package>", github_url="https://github.com/org/repo")
```

This will:
1. Crawl PyPI metadata, ReadTheDocs/Sphinx API pages, GitHub README,
   source code signatures, and docs/examples folders
2. Feed all scraped content to an LLM documentation analyst
3. Extract **Core Classes**, **Key Functions**, **Common Pitfalls**,
   and **Quick-Start Recipes** into a structured reference
4. Save it to your docs directory as `<package>_api.md`

### Step 3 — Verify the Result

The tool returns a status dict with `doc_name` and `path`.  Confirm
the document was created:

```
read_doc("<package>_api")
```

### Step 4 — Use the Reference

Consult the ingested reference when writing analysis code:

- Look up exact class constructors and method signatures
- Check the Common Pitfalls section before using unfamiliar APIs
- Use Quick-Start Recipes as starting points for common tasks
- Cite the reference when explaining your code choices

## What It Produces

A `library_api.md`-format reference document with four sections:

| Section | Contents |
|---------|----------|
| **Core Classes** | Main classes with constructors, methods, parameter tables, return types |
| **Key Functions** | Standalone functions with signatures and parameter tables |
| **Common Pitfalls** | Gotchas, naming conflicts, unit mismatches, common mistakes |
| **Quick-Start Recipes** | Copy-paste code snippets for common tasks |

## Requirements

- Requires `sciagent[wizard]` to be installed:
  `pip install sciagent[wizard]`
- Needs network access to crawl documentation sources
- Works best with well-documented packages on PyPI / ReadTheDocs / GitHub

## Domain Customization

<!-- Add domain-specific notes below this line.
     Examples:
     - Preferred libraries: always ingest neo and pyabf for electrophysiology
     - Custom sources: add github_url for internal/private packages
     - Post-ingestion steps: after ingesting, also check for domain-specific
       tutorials or cookbooks
-->
