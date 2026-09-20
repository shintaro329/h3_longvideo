"""编排 storyboard、H3 窗口生成、恢复和最终媒体合成。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assets import select_active_assets
from .constants import (
    DEFAULT_CHUNK_COUNT,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_HEIGHT,
    DEFAULT_SEED,
    DEFAULT_WIDTH,
    MODEL_ID,
    FPS,
)
from .errors import ConfigurationError
from .h3_adapter import generate_chunk, load_pipeline
from .manifest import read_json, write_json_atomic
from .media_edit import extract_tail, stitch_chunks
from .media_probe import ensure_media_tools, has_audio_stream, validate_media
from .prompting import build_prompt
from .references import build_references
from .scheduler import make_chunks
from .storyboard import load_storyboard


@dataclass(frozen=True)
class RunConfig:
    """描述一次 baseline 运行的所有外部参数。"""

    storyboard_path: Path
    output_dir: Path
    model_id: str = MODEL_ID
    device: str = "cuda"
    dtype: str = "bfloat16"
    height: int = DEFAULT_HEIGHT
    width: int = DEFAULT_WIDTH
    chunk_seconds: float = 14.375
    chunks: int = DEFAULT_CHUNK_COUNT
    seed: int = DEFAULT_SEED
    dry_run: bool = False
    resume: bool = False
    skip_stitch: bool = False


def _write_prompt_files(
    storyboard: Any,
    chunks: tuple[Any, ...],
    output_dir: Path,
    video_audio_ids: set[str],
) -> dict[int, str]:
    """生成每个窗口的 prompt 文件并返回内存中的 prompt。"""

    prompts: dict[int, str] = {}
    for chunk in chunks:
        assets = select_active_assets(storyboard, chunk)
        prompt = build_prompt(
            storyboard,
            chunk,
            assets,
            has_tail=chunk.index > 0,
            tail_has_audio=chunk.index > 0 and storyboard.master_audio is None,
            video_audio_ids=video_audio_ids,
        )
        prompts[chunk.index] = prompt
        (output_dir / f"chunk_{chunk.index + 1:02d}.prompt.txt").write_text(
            prompt,
            encoding="utf-8",
        )
    return prompts


def _collect_video_audio_ids(storyboard: Any) -> set[str]:
    """收集带音轨的视频资产 ID。"""

    return {
        asset.asset_id
        for asset in storyboard.assets
        if asset.kind == "video" and has_audio_stream(asset.path)
    }


def _path_signature(path: Path) -> dict[str, Any]:
    """返回用于恢复校验的轻量文件指纹。"""

    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": str(path), "missing": True}
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _run_fingerprint(storyboard: Any, chunks: tuple[Any, ...], config: RunConfig) -> str:
    """计算一次生成输入的稳定指纹。"""

    payload = {
        "storyboard_sha256": hashlib.sha256(
            storyboard.source_path.read_bytes()
        ).hexdigest(),
        "model_id": config.model_id,
        "device": config.device,
        "dtype": config.dtype,
        "height": config.height,
        "width": config.width,
        "chunk_seconds": config.chunk_seconds,
        "chunks": config.chunks,
        "seed": config.seed,
        "skip_stitch": config.skip_stitch,
        "chunk_plan": [chunk.as_json() for chunk in chunks],
        "assets": [_path_signature(asset.path) for asset in storyboard.assets],
        "master_audio": (
            _path_signature(storyboard.master_audio)
            if storyboard.master_audio is not None
            else None
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _initial_manifest(
    storyboard: Any,
    chunks: tuple[Any, ...],
    config: RunConfig,
    output_dir: Path,
    fingerprint: str,
) -> dict[str, Any]:
    """构造运行初始状态，便于失败后恢复。"""

    return {
        "status": "planned",
        "created_at_unix": time.time(),
        "storyboard": str(storyboard.source_path),
        "model_id": config.model_id,
        "fps": FPS,
        "duration_s": storyboard.duration_s,
        "chunk_seconds": chunks[0].chunk_s,
        "num_chunks": len(chunks),
        "overlap_seconds": chunks[1].overlap_s if len(chunks) > 1 else 0.0,
        "output_dir": str(output_dir),
        "fingerprint": fingerprint,
        "chunks": [],
    }


def run_pipeline(config: RunConfig) -> int:
    """执行一次干跑或真实的可恢复生成流程。"""

    storyboard = load_storyboard(
        config.storyboard_path,
        require_paths=not config.dry_run,
    )
    if config.height % 32 or config.width % 32:
        raise ConfigurationError("height 和 width 必须是 32 的倍数")
    chunks = make_chunks(
        storyboard.duration_s,
        chunk_s=config.chunk_seconds,
        num_chunks=config.chunks,
    )

    output_dir = config.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    fingerprint = _run_fingerprint(storyboard, chunks, config)
    if config.resume:
        if not manifest_path.exists():
            raise ConfigurationError("--resume 要求 output-dir 中已有 manifest.json")
        try:
            manifest = read_json(manifest_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"无法读取 resume manifest：{manifest_path}") from exc
        if not isinstance(manifest, dict) or manifest.get("fingerprint") != fingerprint:
            raise ConfigurationError(
                "resume 指纹不匹配；请使用相同 storyboard、资产、模型参数和 seed，"
                "或指定新的 output-dir"
            )
    else:
        manifest = _initial_manifest(
            storyboard,
            chunks,
            config,
            output_dir,
            fingerprint,
        )
        write_json_atomic(manifest_path, manifest)

    print(f"目标：{storyboard.duration_s:.3f}s @ {FPS} FPS")
    for chunk in chunks:
        print(
            f"窗口 {chunk.index + 1}：[{chunk.start_s:.3f}, {chunk.end_s:.3f}) "
            f"frames={chunk.num_frames} overlap={chunk.overlap_s:.3f}s"
        )

    if config.dry_run:
        video_audio_ids: set[str] = set()
    else:
        ensure_media_tools()
        video_audio_ids = _collect_video_audio_ids(storyboard)
    prompts = _write_prompt_files(
        storyboard,
        chunks,
        output_dir,
        video_audio_ids,
    )
    write_json_atomic(
        output_dir / "chunk_plan.json",
        {
            "storyboard": str(storyboard.source_path),
            "chunks": [chunk.as_json() for chunk in chunks],
            "overlap_s": chunks[1].overlap_s if len(chunks) > 1 else 0.0,
        },
    )
    if config.dry_run:
        print(f"干跑完成：{output_dir}")
        return 0

    pipeline: Any | None = None
    torch_module: Any | None = None
    manifest["status"] = "running"
    write_json_atomic(manifest_path, manifest)

    chunk_paths: list[Path] = []
    for chunk in chunks:
        chunk_path = output_dir / f"chunk_{chunk.index + 1:02d}.mp4"
        chunk_paths.append(chunk_path)
        previous_tail = (
            output_dir / f"tail_{chunk.index:02d}.mp4" if chunk.index > 0 else None
        )

        if config.resume and chunk_path.exists():
            print(f"恢复已有窗口：{chunk_path}")
        else:
            if pipeline is None or torch_module is None:
                pipeline, torch_module = load_pipeline(
                    config.model_id,
                    config.device,
                    config.dtype,
                )
            references = build_references(
                select_active_assets(storyboard, chunk),
                previous_tail,
            )
            seed = config.seed + chunk.index
            print(f"生成窗口 {chunk.index + 1}/{len(chunks)}，seed={seed}")
            generate_chunk(
                pipeline,
                torch_module,
                prompts[chunk.index],
                references,
                chunk_path,
                chunk=chunk,
                seed=seed,
                device=config.device,
                height=config.height,
                width=config.width,
            )

        chunk_media = validate_media(
            chunk_path,
            expected_duration_s=chunk.chunk_s,
            duration_tolerance_s=0.20,
            require_audio=True,
        )
        record = {
            "index": chunk.index,
            "path": str(chunk_path),
            "prompt_path": str(output_dir / f"chunk_{chunk.index + 1:02d}.prompt.txt"),
            "seed": config.seed + chunk.index,
            "start_s": chunk.start_s,
            "end_s": chunk.end_s,
            "media": chunk_media,
            "status": "done",
        }
        manifest["chunks"] = [
            item for item in manifest["chunks"] if item["index"] != chunk.index
        ]
        manifest["chunks"].append(record)
        manifest["chunks"].sort(key=lambda item: item["index"])
        write_json_atomic(manifest_path, manifest)

        if chunk.index < len(chunks) - 1:
            next_overlap = chunks[chunk.index + 1].overlap_s
            tail_path = output_dir / f"tail_{chunk.index + 1:02d}.mp4"
            extract_tail(
                chunk_path,
                tail_path,
                next_overlap,
                with_audio=storyboard.master_audio is None,
            )

    if not config.skip_stitch:
        final_path = output_dir / "final_60s.mp4"
        stitch_chunks(
            chunk_paths,
            final_path,
            chunk_s=chunks[0].chunk_s,
            overlap_s=chunks[1].overlap_s,
            target_s=storyboard.duration_s,
            master_audio=storyboard.master_audio,
        )
        final_media = validate_media(
            final_path,
            expected_duration_s=storyboard.duration_s,
            duration_tolerance_s=0.20,
            require_audio=True,
        )
        manifest["final_path"] = str(final_path)
        manifest["final_media"] = final_media
        manifest["status"] = "complete"
    else:
        manifest["status"] = "chunks_complete"
    write_json_atomic(manifest_path, manifest)
    print(f"完成：{manifest['status']}；manifest={manifest_path}")
    return 0
