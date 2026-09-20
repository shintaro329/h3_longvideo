"""提供 h3-long-video 命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from .constants import (
    DEFAULT_CHUNK_COUNT,
    DEFAULT_HEIGHT,
    DEFAULT_SEED,
    DEFAULT_WIDTH,
    H3_SAFE_CHUNK_SECONDS,
    MODEL_ID,
)
from .errors import ConfigurationError, RuntimeDependencyError
from .runner import RunConfig, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="MiniMax H3 60 秒窗口编排 baseline")
    parser.add_argument("storyboard", type=Path, help="60 秒 storyboard JSON 路径")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/h3_60s"))
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        choices=["bfloat16", "float16", "float32"],
    )
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--chunk-seconds", type=float, default=H3_SAFE_CHUNK_SECONDS)
    parser.add_argument("--chunks", type=int, default=DEFAULT_CHUNK_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只校验 storyboard 和窗口计划，不加载模型",
    )
    parser.add_argument("--resume", action="store_true", help="复用已有窗口产物")
    parser.add_argument("--skip-stitch", action="store_true", help="只生成窗口")
    return parser


def main() -> int:
    """解析参数并返回稳定的进程退出码。"""

    args = build_parser().parse_args()
    config = RunConfig(
        storyboard_path=args.storyboard,
        output_dir=args.output_dir,
        model_id=args.model_id,
        device=args.device,
        dtype=args.dtype,
        height=args.height,
        width=args.width,
        chunk_seconds=args.chunk_seconds,
        chunks=args.chunks,
        seed=args.seed,
        dry_run=args.dry_run,
        resume=args.resume,
        skip_stitch=args.skip_stitch,
    )
    try:
        return run_pipeline(config)
    except (ConfigurationError, RuntimeDependencyError) as exc:
        print(f"错误：{exc}")
        return 2

