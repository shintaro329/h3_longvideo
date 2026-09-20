"""根据窗口时间选择持久资产和局部资产。"""

from __future__ import annotations

from .schemas import Asset, ChunkSpec, Storyboard


def _intersects(
    start_s: float,
    end_s: float,
    other_start: float | None,
    other_end: float | None,
) -> bool:
    """判断两个半开时间区间是否相交。"""

    if other_start is None or other_end is None:
        return True
    return start_s < other_end and end_s > other_start


def select_active_assets(
    storyboard: Storyboard,
    chunk: ChunkSpec,
) -> tuple[Asset, ...]:
    """保留持久资产，并选择当前窗口涉及的 transient 资产。"""

    selected_ids = {
        asset_id
        for shot in storyboard.shots
        if _intersects(chunk.start_s, chunk.end_s, shot.start_s, shot.end_s)
        for asset_id in shot.asset_ids
    }
    selected: list[Asset] = []
    for asset in storyboard.assets:
        if asset.role == "persistent":
            selected.append(asset)
        elif asset.asset_id in selected_ids and _intersects(
            chunk.start_s,
            chunk.end_s,
            asset.start_s,
            asset.end_s,
        ):
            selected.append(asset)
    return tuple(selected)

