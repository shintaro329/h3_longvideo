# Maintenance Guide

## Naming and file ownership

- Python filenames, identifiers, class names, and variables use English.
- Comments and docstrings use Chinese.
- Each Python file owns one core responsibility.
- Shared behavior is imported from the owning module; downstream files must not copy it.
- Heavy runtime dependencies remain lazy imports so CPU-only checks stay lightweight.

## Change procedure

1. Update the schema or contract document before changing the runtime behavior.
2. Add or update a CPU-only test for deterministic logic.
3. Run syntax compilation and dry-run validation.
4. Run the real model only on an explicitly provisioned GPU environment.
5. Save model revision, dependency revisions, resolved assets, prompts, seeds, timings, media metadata, and manifest state with every real run.

## What belongs in Git

Commit source code, public example configurations, documentation, tests, and small metadata files. Do not commit H3 weights, generated videos, raw private assets, API keys, local caches, or experiment outputs.

## Future training boundary

The `training/` directory is reserved for frozen-Base continuation LoRA work. A training implementation must document the dataset manifest, frame-grid contract, previous-tail construction, target window, adapter insertion points, checkpoint format, and evaluation protocol before it is connected to `h3_adapter.py`.

