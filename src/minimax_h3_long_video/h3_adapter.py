"""封装 MiniMax H3 Diffusers 的加载和单窗口生成。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .constants import FPS
from .errors import ConfigurationError, RuntimeDependencyError
from .schemas import ChunkSpec


def load_pipeline(model_id: str, device: str, dtype_name: str) -> tuple[Any, Any]:
    """只加载 H3 Ref2VA 分区，并保持重型依赖延迟导入。"""

    try:
        import torch
        from diffusers import ComponentsManager, ModularPipeline
    except ImportError as exc:
        raise RuntimeDependencyError(
            "真实生成需要 torch 和支持 MiniMax H3 的 Diffusers；干跑不需要这些依赖"
        ) from exc

    if not hasattr(torch, dtype_name):
        raise ConfigurationError(f"torch 没有 dtype：{dtype_name}")
    dtype = getattr(torch, dtype_name)
    manager = ComponentsManager()
    if device.startswith("cuda"):
        manager.enable_auto_cpu_offload(device=device)
    pipeline = ModularPipeline.from_pretrained(
        model_id,
        workflow="ref2va",
        components_manager=manager,
    )
    pipeline.load_components(dtype=dtype)
    return pipeline, torch


def generate_chunk(
    pipeline: Any,
    torch_module: Any,
    prompt: str,
    references: Sequence[Any],
    output_path: Path,
    *,
    chunk: ChunkSpec,
    seed: int,
    device: str,
    height: int,
    width: int,
) -> None:
    """调用一次 H3 Ref2VA 并将视频和音频编码为 MP4。"""

    try:
        from diffusers.utils.export_utils import encode_video
    except ImportError as exc:
        raise RuntimeDependencyError("当前 Diffusers 没有 encode_video") from exc

    generator = torch_module.Generator(device=device).manual_seed(seed)
    result = pipeline(
        prompt=prompt,
        references=list(references),
        num_frames=chunk.num_frames,
        height=height,
        width=width,
        generator=generator,
        output=["videos", "audio", "sampling_rate"],
    )
    encode_video(
        result["videos"][0],
        fps=FPS,
        output_path=str(output_path),
        audio=result["audio"][0],
        audio_sample_rate=result["sampling_rate"],
    )

