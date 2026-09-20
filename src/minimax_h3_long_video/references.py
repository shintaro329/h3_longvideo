"""构造 H3 Ref2VA 参考对象并检查官方数量和时长限制。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .constants import (
    H3_MAX_AUDIOS,
    H3_MAX_IMAGES,
    H3_MAX_REFERENCES,
    H3_MAX_VIDEOS,
)
from .errors import ConfigurationError, RuntimeDependencyError
from .media_probe import media_duration
from .schemas import Asset


def build_references(
    assets: Sequence[Asset],
    previous_tail: Path | None,
) -> list[Any]:
    """按固定顺序创建 continuation、图片、视频和音频参考。"""

    images = [asset for asset in assets if asset.kind == "image"]
    videos = [asset for asset in assets if asset.kind == "video"]
    audios = [asset for asset in assets if asset.kind == "audio"]
    if len(images) > H3_MAX_IMAGES:
        raise ConfigurationError(f"Ref2VA 图片参考最多为 {H3_MAX_IMAGES} 个")
    if len(videos) + int(previous_tail is not None) > H3_MAX_VIDEOS:
        raise ConfigurationError(f"Ref2VA 视频参考最多为 {H3_MAX_VIDEOS} 个")
    if len(audios) > H3_MAX_AUDIOS:
        raise ConfigurationError(f"Ref2VA 音频参考最多为 {H3_MAX_AUDIOS} 个")
    total = len(images) + len(videos) + len(audios) + int(previous_tail is not None)
    if total > H3_MAX_REFERENCES:
        raise ConfigurationError(f"Ref2VA 总参考数最多为 {H3_MAX_REFERENCES} 个")
    if total == 0:
        raise ConfigurationError("Ref2VA 至少需要一个图片或视频参考")
    if audios and not images and not videos and previous_tail is None:
        raise ConfigurationError("Ref2VA 音频参考不能单独使用，至少需要一个图片或视频参考")

    video_paths = ([previous_tail] if previous_tail is not None else []) + [
        asset.path for asset in videos
    ]
    video_duration_total = 0.0
    for path in video_paths:
        duration_s = media_duration(path)
        if not 2.0 <= duration_s <= 15.2:
            raise ConfigurationError(
                f"视频参考 {path} 时长为 {duration_s:.3f}s，不在 2–15s 范围内"
            )
        video_duration_total += duration_s
    if video_duration_total > 15.2:
        raise ConfigurationError(
            f"视频参考总时长为 {video_duration_total:.3f}s，超过 Ref2VA 的 15s 限制"
        )

    audio_duration_total = 0.0
    for asset in audios:
        duration_s = media_duration(asset.path)
        if not 2.0 <= duration_s <= 15.0:
            raise ConfigurationError(
                f"音频参考 {asset.path} 时长为 {duration_s:.3f}s，不在 2–15s 范围内"
            )
        audio_duration_total += duration_s
    if audio_duration_total > 15.0:
        raise ConfigurationError(
            f"音频参考总时长为 {audio_duration_total:.3f}s，超过 Ref2VA 的 15s 限制"
        )

    try:
        from diffusers.modular_pipelines.minimax_h3 import (
            MiniMaxH3AudioReference,
            MiniMaxH3ImageReference,
            MiniMaxH3VideoReference,
        )
    except ImportError as exc:
        raise RuntimeDependencyError(
            "当前 Diffusers 没有 MiniMax H3 reference classes；请安装支持 H3 的版本"
        ) from exc

    references: list[Any] = []
    if previous_tail is not None:
        references.append(MiniMaxH3VideoReference.from_file(str(previous_tail)))
    references.extend(
        MiniMaxH3ImageReference.from_file(str(asset.path)) for asset in images
    )
    references.extend(
        MiniMaxH3VideoReference.from_file(str(asset.path)) for asset in videos
    )
    references.extend(
        MiniMaxH3AudioReference.from_file(str(asset.path)) for asset in audios
    )
    return references
