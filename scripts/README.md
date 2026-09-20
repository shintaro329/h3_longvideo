# Maintenance Scripts

This directory is reserved for small, reproducible shell or Python entry points such as environment checks, dry-run validation, data manifest generation, and training launch wrappers.

Scripts should call package APIs instead of duplicating runtime logic. Machine-specific paths and secrets must be passed through arguments or environment variables and must not be committed.

