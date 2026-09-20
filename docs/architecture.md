# Architecture

## Runtime flow

```text
storyboard.json
      │
      ▼
storyboard.py ──► scheduler.py ──► ChunkSpec[1..5]
      │                                  │
      ├────────► assets.py ──────────────┤
      ├────────► prompting.py ───────────┤
      │                                  ▼
      │                         h3_adapter.py
      │                                  │
      │                    chunk MP4 + audio outputs
      │                                  │
      └────────► references.py ◄── previous tail
                                         │
                                         ▼
                         media_probe.py / media_edit.py
                                         │
                                         ▼
                              final_60s.mp4 + manifest
```

## Module ownership

| Module | Single responsibility | Main interface |
|---|---|---|
| `schemas.py` | Typed data records | `Asset`, `Shot`, `Storyboard`, `ChunkSpec` |
| `storyboard.py` | JSON parsing and validation | `load_storyboard` |
| `scheduler.py` | H3 frame alignment and window schedule | `align_frame_count`, `make_chunks` |
| `assets.py` | Window-dependent asset selection | `select_active_assets` |
| `prompting.py` | Local full-reference prompt assembly | `build_prompt` |
| `references.py` | H3 reference construction and limits | `build_references` |
| `h3_adapter.py` | Model loading and one H3 request | `load_pipeline`, `generate_chunk` |
| `media_probe.py` | Media metadata and validation | `probe_media`, `validate_media` |
| `media_edit.py` | ffmpeg operations | `extract_tail`, `stitch_chunks` |
| `manifest.py` | Atomic run-state persistence | `write_json_atomic` |
| `runner.py` | Cross-module orchestration | `run_pipeline` |
| `cli.py` | User-facing CLI | `main` |

## Dependency direction

Lower-level modules do not import `runner.py` or `cli.py`. `h3_adapter.py` and `references.py` are the only modules that import heavy H3 runtime libraries, and those imports happen inside functions. This allows the schema, scheduler, prompt, and media-contract checks to run without model weights.

## Continuation contract

Every continuation request receives the previous chunk tail first, then persistent assets, then window-local assets. The order is recorded by prompt and manifest. A future continuation LoRA must preserve this contract rather than silently changing the inference protocol.

