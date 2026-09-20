# MiniMax H3 Long Video

An inference pipeline that turns a 60-second storyboard and reference assets into a 60-second video by orchestrating multiple MiniMax H3 Ref2VA windows.

The pipeline keeps each H3 request within the supported window and reference limits, carries visual continuity through the previous window tail, and stitches the generated windows into one MP4 file.

## What it provides

- Validates a 60-second storyboard, shot timeline, assets, and reference constraints.
- Splits the timeline into five H3-compatible windows: 345 frames / 14.375 seconds per window at 24 FPS, with a 2.96875-second overlap.
- Routes persistent and time-scoped image, video, and audio references to each window.
- Detects audio streams in video references and keeps H3 `<Audio N>` prompt labels aligned with the reference order.
- Generates a continuation tail after every window for the next Ref2VA request.
- Uses `ffmpeg` to crossfade the windows and produce `final_60s.mp4`.
- Supports interruption recovery through `--resume` and a manifest fingerprint.
- Provides dry-run, CPU-only contract tests, and a CI workflow.

## Pipeline

```text
storyboard.json
      │
      ▼
validate + schedule H3 windows
      │
      ├── select active references
      ├── build window prompt
      └── generate one H3 Ref2VA window
                    │
                    ├── save chunk MP4
                    └── extract continuation tail
                              │
                              ▼
                    crossfade chunks with ffmpeg
                              │
                              ▼
                         final_60s.mp4
```

## Requirements

- Python 3.10 or newer.
- For dry-run and tests: Python standard library only.
- For generation: PyTorch, a Diffusers version with MiniMax H3 support, `ffmpeg`, and `ffprobe`.
- A device and model environment that can load `MiniMaxAI/MiniMax-H3` or another compatible H3 model.

The repository does not include model weights or media assets. The default model is `MiniMaxAI/MiniMax-H3`; review the upstream model license before use.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate

# CPU checks and tests
pip install -e ".[dev]"

# Runtime dependencies for generation
pip install -e ".[runtime]"
```

Check the external tools before a real run:

```bash
ffmpeg -version
ffprobe -version
```

## Quick start

### Dry-run

The dry-run validates the storyboard and writes the planned prompts and chunk schedule without loading model weights or reading real media files:

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.example.json \
  --dry-run \
  --output-dir outputs/h3_60s_dry_run
```

### Generate a video

Copy `configs/storyboard.example.json`, replace the asset paths with real files, and run:

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --model-id MiniMaxAI/MiniMax-H3 \
  --device cuda \
  --dtype bfloat16
```

The installed console entry point is also available:

```bash
h3-long-video configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16
```

### Resume an interrupted run

Use the same storyboard, assets, model options, chunk options, and seed:

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16 \
  --resume
```

`--resume` requires `manifest.json` in the output directory. Existing chunks are reused only when the run fingerprint matches the storyboard, generation options, chunk plan, and asset path metadata. A mismatch stops the run to prevent mixing outputs from different inputs. Completed chunks are media-validated before reuse, and continuation tails are regenerated from the current chunks.

### Generate chunks without stitching

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/chunks_only \
  --device cuda \
  --dtype bfloat16 \
  --skip-stitch
```

## Storyboard format

Use [`configs/storyboard.example.json`](configs/storyboard.example.json) as the complete template. The top-level fields are:

| Field | Description |
|---|---|
| `duration_s` | Must be `60`. |
| `fps` | Must be `24`. |
| `global_prompt` | Global visual and motion instructions. |
| `continuity` | Optional continuity instructions such as character, environment, camera, lighting, color, and audio. |
| `assets` | Reference assets used by the windows. |
| `shots` | Ordered, gap-free shot intervals covering `[0, 60)`. |
| `master_audio` | Optional final soundtrack path. When set, it replaces generated chunk audio during final stitching. |

Each asset has the following shape:

```json
{
  "id": "hero",
  "kind": "image",
  "path": "../data/examples/assets/hero.png",
  "role": "persistent",
  "description": "the main character reference"
}
```

Supported `kind` values are `image`, `video`, and `audio`. A `transient` asset must also define `start_s` and `end_s`; it is included only in overlapping windows. Each shot uses `asset_ids` to select the references active in that shot.

Reference validation follows the H3 Ref2VA contract:

- Up to 9 image references, 3 video references, 3 audio references, and 12 total references per request.
- Video references must each be 2–15.2 seconds, with a total of 15.2 seconds or less; each video is checked before the model call.
- Each explicit audio reference must be 2–15 seconds, and explicit audio must be 15 seconds or less in total.
- An explicit audio reference cannot be the only reference in a request.

## Command-line options

| Option | Default | Description |
|---|---:|---|
| `--output-dir` | `outputs/h3_60s` | Directory for prompts, chunks, tails, manifest, and final video. |
| `--model-id` | `MiniMaxAI/MiniMax-H3` | H3 model identifier. |
| `--device` | `cuda` | Torch device. |
| `--dtype` | `bfloat16` | `bfloat16`, `float16`, or `float32`. |
| `--height` | `768` | Output height; must be divisible by 32. |
| `--width` | `1344` | Output width; must be divisible by 32. |
| `--chunk-seconds` | `14.375` | H3 window duration. |
| `--chunks` | `5` | Number of windows. |
| `--seed` | `20260920` | Base seed; window `i` uses `seed + i`. |
| `--dry-run` | off | Validate and plan without model inference. |
| `--resume` | off | Reuse compatible completed chunks. |
| `--skip-stitch` | off | Stop after chunk generation. |

## Output files

A completed run normally contains:

```text
outputs/my_60s_run/
├── manifest.json
├── chunk_plan.json
├── chunk_01.prompt.txt ... chunk_05.prompt.txt
├── chunk_01.mp4 ... chunk_05.mp4
├── tail_01.mp4 ... tail_04.mp4
└── final_60s.mp4
```

`manifest.json` records the run fingerprint, chunk status, media metadata, and final output status. Generated media and run directories are ignored by Git.

## Code map

| Path | Responsibility |
|---|---|
| `src/minimax_h3_long_video/cli.py` | Parses command-line arguments and starts a run. |
| `src/minimax_h3_long_video/runner.py` | Coordinates validation, scheduling, generation, resume, and stitching. |
| `src/minimax_h3_long_video/storyboard.py` | Loads and validates the storyboard JSON. |
| `src/minimax_h3_long_video/schemas.py` | Defines storyboard, asset, shot, and chunk records. |
| `src/minimax_h3_long_video/scheduler.py` | Aligns frame counts and creates the H3 window plan. |
| `src/minimax_h3_long_video/assets.py` | Selects persistent and time-scoped assets for each window. |
| `src/minimax_h3_long_video/prompting.py` | Builds deterministic prompts and reference labels. |
| `src/minimax_h3_long_video/references.py` | Validates and constructs H3 Ref2VA references. |
| `src/minimax_h3_long_video/media_probe.py` | Reads media metadata and validates durations and streams. |
| `src/minimax_h3_long_video/h3_adapter.py` | Loads Diffusers and executes one H3 generation request. |
| `src/minimax_h3_long_video/media_edit.py` | Extracts tails and stitches MP4 windows with ffmpeg. |
| `src/minimax_h3_long_video/manifest.py` | Reads and atomically writes run state. |
| `tests/` | CPU-only tests for scheduling, storyboard validation, and runtime contracts. |

## Verification

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests -v
./scripts/check_dry_run.sh
```

## Related projects

- [MiniMax H3](https://github.com/MiniMax-AI/MiniMax-H3)
- [Diffusers MiniMax H3 pipeline](https://huggingface.co/docs/diffusers/main/en/api/pipelines/minimax_h3)
- [VDN-Minimax-H3](https://github.com/OpenVDN/vdn-minimax-h3)
