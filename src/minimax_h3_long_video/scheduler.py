"""计算 H3 合法帧数和 60 秒重叠窗口。"""

from __future__ import annotations

from .constants import (
    FPS,
    H3_FRAME_OFFSET,
    H3_FRAME_STRIDE,
    H3_MAX_SECONDS,
    H3_MIN_SECONDS,
    H3_SAFE_CHUNK_SECONDS,
)
from .errors import ConfigurationError
from .schemas import ChunkSpec


def align_frame_count(requested_frames: int) -> int:
    """向上对齐到 H3 VAE 支持的 17n+5 帧网格。"""

    if requested_frames < 1:
        raise ConfigurationError(f"num_frames 必须为正数，实际为 {requested_frames}")
    aligned_frames = requested_frames
    while aligned_frames % H3_FRAME_STRIDE != H3_FRAME_OFFSET:
        aligned_frames += 1
    return aligned_frames


def make_chunks(
    duration_s: float,
    *,
    chunk_s: float = H3_SAFE_CHUNK_SECONDS,
    num_chunks: int = 5,
) -> tuple[ChunkSpec, ...]:
    """创建精确覆盖目标时长的 H3 窗口计划。"""

    if not H3_MIN_SECONDS <= chunk_s <= H3_MAX_SECONDS:
        raise ConfigurationError(
            f"chunk_s 必须在 [{H3_MIN_SECONDS}, {H3_MAX_SECONDS}] 内，实际为 {chunk_s}"
        )
    if num_chunks < 2:
        raise ConfigurationError("num_chunks 至少为 2")

    requested_frames = max(1, int(round(chunk_s * FPS)))
    aligned_frames = align_frame_count(requested_frames)
    aligned_chunk_s = aligned_frames / FPS
    if not H3_MIN_SECONDS <= aligned_chunk_s <= H3_MAX_SECONDS:
        raise ConfigurationError(
            f"请求的 chunk_s={requested_frames / FPS:.6f}s 对齐到 "
            f"{aligned_frames} 帧（{aligned_chunk_s:.6f}s），超出当前 Diffusers 的 "
            f"{H3_MIN_SECONDS:g}-{H3_MAX_SECONDS:g}s 契约；请使用不超过 "
            f"{H3_SAFE_CHUNK_SECONDS:.6f}s 的窗口"
        )

    overlap_s = (num_chunks * aligned_chunk_s - duration_s) / (num_chunks - 1)
    if not 2.0 <= overlap_s < aligned_chunk_s:
        raise ConfigurationError(
            f"计算得到 overlap={overlap_s:.6f}s 无效，需要满足 2s <= overlap < chunk_s"
        )

    stride_s = aligned_chunk_s - overlap_s
    specs: list[ChunkSpec] = []
    for index in range(num_chunks):
        start_s = index * stride_s
        end_s = start_s + aligned_chunk_s
        if index == num_chunks - 1:
            end_s = duration_s
            start_s = end_s - aligned_chunk_s
        specs.append(
            ChunkSpec(
                index=index,
                start_s=round(start_s, 6),
                end_s=round(end_s, 6),
                chunk_s=round(aligned_chunk_s, 6),
                overlap_s=round(overlap_s if index else 0.0, 6),
                num_frames=aligned_frames,
            )
        )
    if abs(specs[-1].end_s - duration_s) > 1e-4:
        raise ConfigurationError("窗口计划没有结束于目标时长")
    return tuple(specs)

