"""使用 ffprobe 读取媒体元数据并校验生成产物。"""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path
from shutil import which
from typing import Any

from .constants import FPS
from .errors import RuntimeDependencyError


def ensure_media_tools() -> None:
    """确认 ffmpeg 和 ffprobe 可执行。"""

    missing = [name for name in ("ffmpeg", "ffprobe") if which(name) is None]
    if missing:
        raise RuntimeDependencyError(
            f"缺少媒体工具：{', '.join(missing)}；请先安装 ffmpeg"
        )


def probe_media(path: Path) -> dict[str, Any]:
    """读取媒体流和容器元数据，不解码视频内容。"""

    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeDependencyError("找不到 ffprobe") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeDependencyError(f"ffprobe 读取失败：{path}: {detail}") from exc
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeDependencyError(f"ffprobe 返回了无效 JSON：{path}") from exc


def media_duration(path: Path) -> float:
    """读取媒体容器报告的时长。"""

    metadata = probe_media(path)
    value = metadata.get("format", {}).get("duration")
    if value is None:
        raise RuntimeDependencyError(f"ffprobe 没有返回时长：{path}")
    return float(value)


def has_audio_stream(path: Path) -> bool:
    """判断媒体是否包含音频流。"""

    metadata = probe_media(path)
    return any(
        stream.get("codec_type") == "audio"
        for stream in metadata.get("streams", [])
    )


def validate_media(
    path: Path,
    *,
    expected_duration_s: float | None = None,
    duration_tolerance_s: float = 0.15,
    require_audio: bool = True,
) -> dict[str, Any]:
    """校验视频、音频、帧率和目标时长。"""

    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeDependencyError(f"媒体输出缺失或为空：{path}")
    metadata = probe_media(path)
    streams = metadata.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise RuntimeDependencyError(f"媒体输出没有视频流：{path}")
    if require_audio and not audio_streams:
        raise RuntimeDependencyError(f"媒体输出没有音频流：{path}")

    video = video_streams[0]
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
    actual_fps = None
    if rate and rate != "0/0":
        actual_fps = float(Fraction(rate))
        if abs(actual_fps - FPS) > 0.05:
            raise RuntimeDependencyError(
                f"期望 {FPS} FPS，实际为 {actual_fps:.4f}：{path}"
            )

    format_duration = metadata.get("format", {}).get("duration")
    actual_duration = float(format_duration) if format_duration else None
    if expected_duration_s is not None and actual_duration is not None:
        if abs(actual_duration - expected_duration_s) > duration_tolerance_s:
            raise RuntimeDependencyError(
                f"期望时长 {expected_duration_s:.3f}s，实际为 {actual_duration:.3f}s：{path}"
            )
    return {
        "path": str(path),
        "duration_s": actual_duration,
        "fps": actual_fps,
        "has_audio": bool(audio_streams),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
    }
