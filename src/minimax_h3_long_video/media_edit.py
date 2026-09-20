"""使用 ffmpeg 抽取 continuation 尾部并合成最终视频。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Sequence

from .errors import RuntimeDependencyError


def _run_checked(command: Sequence[str]) -> None:
    """执行外部媒体命令并保留可诊断错误。"""

    try:
        completed = subprocess.run(
            list(command),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeDependencyError(f"找不到外部命令：{command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeDependencyError(
            f"媒体命令失败（退出码 {exc.returncode}）：{' '.join(command)}\n{detail}"
        ) from exc
    if completed.stderr and os.environ.get("H3_VERBOSE_FFMPEG"):
        print(completed.stderr)


def extract_tail(
    input_path: Path,
    output_path: Path,
    duration_s: float,
    *,
    with_audio: bool,
) -> None:
    """抽取上一窗口尾部作为下一窗口的 motion reference。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-sseof",
        f"-{duration_s:.6f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration_s:.6f}",
        "-vf",
        "fps=24",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
    ]
    command += ["-c:a", "aac", "-ar", "32000"] if with_audio else ["-an"]
    command.append(str(output_path))
    _run_checked(command)


def stitch_chunks(
    chunk_paths: Sequence[Path],
    output_path: Path,
    *,
    chunk_s: float,
    overlap_s: float,
    target_s: float,
    master_audio: Path | None,
) -> None:
    """用固定 overlap 合成视频，并保持目标时长。"""

    if len(chunk_paths) < 2:
        raise ValueError("至少需要两个 chunk")
    if master_audio is not None and not master_audio.exists():
        raise RuntimeDependencyError(f"master audio 不存在：{master_audio}")

    filters: list[str] = []
    for index in range(len(chunk_paths)):
        filters.append(
            f"[{index}:v]fps=24,format=yuv420p,trim=duration={chunk_s:.6f},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        if master_audio is None:
            filters.append(
                f"[{index}:a]aresample=32000,atrim=duration={chunk_s:.6f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )

    current_video = "v0"
    current_audio = "a0"
    accumulated_s = chunk_s
    for index in range(1, len(chunk_paths)):
        offset_s = accumulated_s - overlap_s
        next_video = f"vx{index}"
        filters.append(
            f"[{current_video}][v{index}]xfade=transition=fade:duration={overlap_s:.6f}:"
            f"offset={offset_s:.6f}[{next_video}]"
        )
        current_video = next_video
        if master_audio is None:
            next_audio = f"ax{index}"
            filters.append(
                f"[{current_audio}][a{index}]acrossfade=d={overlap_s:.6f}:c1=tri:c2=tri[{next_audio}]"
            )
            current_audio = next_audio
        accumulated_s += chunk_s - overlap_s

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in chunk_paths:
        command += ["-i", str(path)]
    if master_audio is not None:
        command += ["-i", str(master_audio)]
    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{current_video}]",
    ]
    command += ["-map", f"{len(chunk_paths)}:a:0"] if master_audio else ["-map", f"[{current_audio}]"]
    command += [
        "-t",
        f"{target_s:.6f}",
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "32000",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run_checked(command)

