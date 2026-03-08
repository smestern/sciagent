## INCREMENTAL EXECUTION PRINCIPLE (MANDATORY)

When processing datasets, work incrementally — never run a full pipeline
before validating on a small sample first.

### Workflow
1. **Examine structure** — Load one representative file/sample and inspect
   its layout, metadata, and content before any analysis.
2. **Validate on one unit** — Run the full analysis on a single unit (one
   sweep, one row, one sample). Show intermediate values and sanity-check
   every result. Get user confirmation.
3. **Small batch test** — Process 2-3 additional units and check
   consistency across them.
4. **Scale** — Only after the user approves steps 1-3, process the full
   dataset with the validated pipeline.

**Always show the user what you found at each stage before proceeding.**
If any value looks anomalous at step 2, STOP and investigate before scaling.
