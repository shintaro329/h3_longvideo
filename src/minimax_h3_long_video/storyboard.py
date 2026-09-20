"""加载并校验 60 秒 storyboard JSON。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import DEFAULT_DURATION_SECONDS, FPS
from .errors import ConfigurationError
from .schemas import Asset, Shot, Storyboard


def _to_float(value: Any, field: str) -> float:
    """将配置字段转换为浮点数并给出统一错误。"""

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{field} 必须是数字，当前为 {value!r}") from exc


def _resolve_path(base_dir: Path, value: Any, field: str) -> Path:
    """将相对资产路径解析到 storyboard 所在目录。"""

    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} 必须是非空路径")
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _validate_interval(
    start_s: float | None,
    end_s: float | None,
    *,
    field: str,
) -> None:
    """校验可选的时间区间。"""

    if start_s is None and end_s is None:
        return
    if start_s is None or end_s is None:
        raise ConfigurationError(f"{field} 必须同时提供 start_s 和 end_s")
    if start_s < 0 or end_s <= start_s:
        raise ConfigurationError(f"{field} 的时间区间无效：[{start_s}, {end_s})")


def load_storyboard(path: Path, *, require_paths: bool) -> Storyboard:
    """读取并校验确定性的 60 秒 storyboard 契约。"""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"storyboard 不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"storyboard JSON 无效：{path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("storyboard 根节点必须是对象")

    duration_s = _to_float(raw.get("duration_s", DEFAULT_DURATION_SECONDS), "duration_s")
    fps = int(raw.get("fps", FPS))
    if abs(duration_s - DEFAULT_DURATION_SECONDS) > 1e-3:
        raise ConfigurationError(
            f"当前 baseline 固定 duration_s=60，实际为 {duration_s}"
        )
    if fps != FPS:
        raise ConfigurationError(f"MiniMax H3 baseline 要求 fps=24，实际为 {fps}")

    global_prompt = str(raw.get("global_prompt", "")).strip()
    if not global_prompt:
        raise ConfigurationError("global_prompt 不能为空")

    continuity_raw = raw.get("continuity", {})
    if not isinstance(continuity_raw, dict):
        raise ConfigurationError("continuity 必须是对象")
    continuity = {
        str(key): str(value).strip()
        for key, value in continuity_raw.items()
        if str(value).strip()
    }

    base_dir = path.parent.resolve()
    assets: list[Asset] = []
    asset_ids: set[str] = set()
    for index, item in enumerate(raw.get("assets", [])):
        if not isinstance(item, dict):
            raise ConfigurationError(f"assets[{index}] 必须是对象")
        asset_id = str(item.get("id", "")).strip()
        if not asset_id or asset_id in asset_ids:
            raise ConfigurationError(f"assets[{index}] 的 id 缺失或重复")
        kind = str(item.get("kind", "image")).strip().lower()
        if kind not in {"image", "video", "audio"}:
            raise ConfigurationError(f"assets[{index}].kind 必须是 image/video/audio")
        role = str(item.get("role", "persistent")).strip().lower()
        if role not in {"persistent", "transient"}:
            raise ConfigurationError(
                f"assets[{index}].role 必须是 persistent/transient"
            )
        start_value = item.get("start_s")
        end_value = item.get("end_s")
        start_s = (
            None if start_value is None else _to_float(start_value, f"assets[{index}].start_s")
        )
        end_s = None if end_value is None else _to_float(end_value, f"assets[{index}].end_s")
        if role == "transient" and (start_s is None or end_s is None):
            raise ConfigurationError(f"transient asset {asset_id!r} 必须有时间区间")
        _validate_interval(start_s, end_s, field=f"assets[{index}]")
        if end_s is not None and end_s > duration_s:
            raise ConfigurationError(f"assets[{index}] 结束时间超过 60 秒")
        asset_path = _resolve_path(base_dir, item.get("path"), f"assets[{index}].path")
        if require_paths and not asset_path.exists():
            raise ConfigurationError(f"资产 {asset_id!r} 不存在：{asset_path}")
        assets.append(
            Asset(
                asset_id=asset_id,
                kind=kind,
                path=asset_path,
                role=role,
                description=str(item.get("description", asset_id)).strip(),
                start_s=start_s,
                end_s=end_s,
            )
        )
        asset_ids.add(asset_id)

    shots_raw = raw.get("shots")
    if not isinstance(shots_raw, list) or not shots_raw:
        raise ConfigurationError("shots 必须是非空数组")
    shots: list[Shot] = []
    cursor = 0.0
    shot_ids: set[str] = set()
    for index, item in enumerate(shots_raw):
        if not isinstance(item, dict):
            raise ConfigurationError(f"shots[{index}] 必须是对象")
        shot_id = str(item.get("id", f"shot_{index + 1}")).strip()
        if shot_id in shot_ids:
            raise ConfigurationError(f"shot id 重复：{shot_id}")
        start_s = _to_float(item.get("start_s"), f"shots[{index}].start_s")
        end_s = _to_float(item.get("end_s"), f"shots[{index}].end_s")
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            raise ConfigurationError(f"shots[{index}].prompt 不能为空")
        if abs(start_s - cursor) > 1e-3:
            raise ConfigurationError(
                f"shots 必须无缝覆盖时间轴：期望 {cursor}，实际 {start_s}"
            )
        if end_s <= start_s or end_s > duration_s:
            raise ConfigurationError(f"shot {shot_id!r} 的时间区间无效")
        referenced = tuple(str(value) for value in item.get("asset_ids", []))
        unknown = sorted(set(referenced) - asset_ids)
        if unknown:
            raise ConfigurationError(f"shot {shot_id!r} 引用了未知资产：{unknown}")
        shots.append(Shot(shot_id, start_s, end_s, prompt, referenced))
        shot_ids.add(shot_id)
        cursor = end_s
    if abs(cursor - duration_s) > 1e-3:
        raise ConfigurationError(f"shots 结束于 {cursor}，但目标为 {duration_s}")

    master_audio_value = raw.get("master_audio")
    master_audio = None
    if master_audio_value is not None:
        master_audio = _resolve_path(base_dir, master_audio_value, "master_audio")
        if require_paths and not master_audio.exists():
            raise ConfigurationError(f"master_audio 不存在：{master_audio}")

    return Storyboard(
        duration_s=duration_s,
        fps=fps,
        global_prompt=global_prompt,
        continuity=continuity,
        assets=tuple(assets),
        shots=tuple(shots),
        master_audio=master_audio,
        source_path=path.resolve(),
    )

