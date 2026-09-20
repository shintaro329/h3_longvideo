# Contributing

## Before opening a change

Read both repository READMEs and `docs/maintenance.md`. Keep model weights, private assets, credentials, and generated videos outside Git.

## Required checks

```bash
./scripts/check_dry_run.sh
python3 -m compileall -q src tests
```

If a change touches real generation, also record the H3 checkpoint revision, Diffusers revision, hardware, resolved storyboard, reference ordering, seeds, per-window timings, media metadata, and boundary checks. Do not report a visual-quality improvement from a dry run.

## Code style

Use English Python identifiers and Chinese comments/docstrings. Keep each Python file focused on one core responsibility. Import shared behavior from its owning module instead of copying it into a downstream script.

