# MiniMax H3 Long Video Pipeline

This repository contains a small, resumable orchestration baseline for producing a 60-second video from a complete storyboard and reference assets with MiniMax H3 Ref2VA.

The baseline keeps every model request inside the public H3 context contract. The current Diffusers integration uses the largest strictly legal aligned request, 345 frames at 24 FPS (14.375 seconds), and composes five overlapping windows:

```text
5 × 14.375 - 4 × 2.96875 = 60 seconds
```

This is an orchestration pipeline, not a native 60-second H3 model. It does not modify H3 Base weights, MM-RoPE, the VAE, or the Attention implementation.

## Quick start

The dry run validates the storyboard, H3 frame grid, asset routing, prompts, and exact timeline without loading model weights:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.example.json \
  --dry-run \
  --output-dir outputs/h3_60s_dry_run
```

For real generation, install the optional runtime dependencies and make `ffmpeg` and `ffprobe` available on `PATH`:

```bash
pip install -e ".[runtime]"

PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16 \
  --resume
```

The example configuration contains placeholder asset paths. Replace them with real files before a non-dry run. No model weights, generated media, or private data belong in Git.

## Repository layout

```text
code/
├── README.md                         # English entry point
├── README.zh-CN.md                   # Chinese entry point
├── pyproject.toml                    # Package and dependency metadata
├── configs/                          # Reproducible public configuration examples
├── src/minimax_h3_long_video/        # Runtime package
│   ├── assets.py                     # Window-local and persistent asset selection
│   ├── cli.py                        # Command-line parsing only
│   ├── constants.py                  # H3 contract and project defaults
│   ├── errors.py                     # Project-level exceptions
│   ├── h3_adapter.py                 # Lazy Diffusers loading and one-window generation
│   ├── manifest.py                   # Atomic resumable manifest writes
│   ├── media_edit.py                 # ffmpeg tail extraction and stitching
│   ├── media_probe.py                # ffprobe metadata and media validation
│   ├── prompting.py                  # Deterministic H3 full-reference prompt composer
│   ├── references.py                 # H3 Ref2VA reference construction and limits
│   ├── runner.py                     # End-to-end orchestration
│   ├── schemas.py                    # Typed storyboard and chunk records
│   ├── scheduler.py                  # VAE-aligned frame count and window planning
│   └── storyboard.py                  # JSON loading and contract validation
├── tests/                            # CPU-only contract tests
├── docs/                             # Architecture and maintenance notes
├── data/                             # Data contract and future dataset placeholders
├── training/                         # Future post-training/LoRA placeholders
├── scripts/                          # Reproducible maintenance entry points
└── outputs/                          # Local generated runs, ignored by Git
```

`CHANGELOG.md` records repository-level changes, `CONTRIBUTING.md` defines the maintenance contract, and `.github/workflows/ci.yml` runs CPU-only compilation and contract tests on every push and pull request.

## Module boundaries

Every Python module has one primary responsibility. Runtime dependencies are imported only in `h3_adapter.py` and `references.py`, so planning and CPU-only tests do not require a GPU or model download. Downstream code imports stable functions from the package instead of duplicating implementation.

Python identifiers and filenames use English. Comments and docstrings are written in Chinese to keep implementation notes consistent for the project team.

## Scope and future extension

The current code implements inference-time orchestration only. The repository reserves `data/` for source media, manifests, latent caches, and evaluation splits, and `training/` for continuation-LoRA datasets, post-training code, and configs. These directories contain contracts and placeholders, not an unverified training implementation.

The next post-training interface should attach a frozen-Base continuation adapter while preserving the same `ChunkSpec`, storyboard, reference ordering, and manifest formats.

## Upstream boundaries

The implementation follows the public MiniMax H3 and Diffusers interfaces. H3 checkpoints and their model license remain upstream assets. Do not commit weights, API credentials, generated private media, or copied upstream source into this repository. Review the upstream license before redistribution.

Related engineering references include [MiniMax H3](https://github.com/MiniMax-AI/MiniMax-H3), [Diffusers MiniMax H3](https://huggingface.co/docs/diffusers/main/en/api/pipelines/minimax_h3), and [VDN-Minimax-H3](https://github.com/OpenVDN/vdn-minimax-h3).
