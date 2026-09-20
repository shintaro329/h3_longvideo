"""定义 storyboard、资产和窗口计划的数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Asset:
    """描述一个 H3 参考资产。"""

    asset_id: str
    kind: str
    path: Path
    role: str
    description: str
    start_s: float | None = None
    end_s: float | None = None

    def as_json(self) -> dict[str, Any]:
        """将路径转换为 JSON 可序列化的字符串。"""

        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class Shot:
    """描述 storyboard 中一个连续 shot。"""

    shot_id: str
    start_s: float
    end_s: float
    prompt: str
    asset_ids: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        """将资产 ID 元组转换为 JSON 数组。"""

        data = asdict(self)
        data["asset_ids"] = list(self.asset_ids)
        return data


@dataclass(frozen=True)
class Storyboard:
    """描述一份完整的 60 秒生成计划。"""

    duration_s: float
    fps: int
    global_prompt: str
    continuity: dict[str, str]
    assets: tuple[Asset, ...]
    shots: tuple[Shot, ...]
    master_audio: Path | None
    source_path: Path


@dataclass(frozen=True)
class ChunkSpec:
    """描述一个合法的 H3 生成窗口。"""

    index: int
    start_s: float
    end_s: float
    chunk_s: float
    overlap_s: float
    num_frames: int

    def as_json(self) -> dict[str, Any]:
        """返回窗口计划的 JSON 表示。"""

        return asdict(self)

