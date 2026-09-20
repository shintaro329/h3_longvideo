# Data Contract

This directory reserves the future data layout. The current inference baseline does not require a committed dataset.

```text
data/
├── examples/assets/       # Local-only placeholder asset paths
├── raw/                   # Ignored source videos, scripts, and references
├── processed/             # Ignored normalized clips and manifests
├── cache/                 # Ignored VAE/text/audio latent caches
├── manifests/             # Public schema examples and private run manifests
└── splits/                # train/validation/test index files
```

Each future sample should record a stable sample ID, source video, 60-second target interval, storyboard version, reference asset manifest, audio source, frame rate, resolution, and license/provenance. Precomputed latents must include the H3 checkpoint revision and preprocessing configuration.

Do not commit raw or private media. The placeholder asset paths in `configs/storyboard.example.json` are intentionally unresolved so the dry run can validate configuration without requiring data.

