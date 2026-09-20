"""将 storyboard 编排为 H3 Ref2VA 结构化 prompt。"""

from __future__ import annotations

from typing import Sequence

from .constants import MAX_PROMPT_CHARS
from .errors import ConfigurationError
from .schemas import Asset, ChunkSpec, Storyboard


def _format_clock(seconds: float) -> str:
    """将秒数格式化为分:秒.毫秒。"""

    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:06.3f}"


def _reference_labels(
    assets: Sequence[Asset],
    has_tail: bool,
    *,
    tail_has_audio: bool = False,
    video_audio_ids: set[str] | None = None,
) -> dict[str, str]:
    """按照 H3 prompt guide 为参考资产分配稳定标签。"""

    labels: dict[str, str] = {}
    video_audio_ids = video_audio_ids or set()
    images = [asset for asset in assets if asset.kind == "image"]
    videos = [asset for asset in assets if asset.kind == "video"]
    audios = [asset for asset in assets if asset.kind == "audio"]
    for index, asset in enumerate(images, start=1):
        labels[asset.asset_id] = f"<Picture {index}>"
    for index, asset in enumerate(videos, start=1 + int(has_tail)):
        labels[asset.asset_id] = f"<Video {index}>"
    audio_index = int(tail_has_audio) + sum(
        asset.asset_id in video_audio_ids for asset in videos
    )
    for index, asset in enumerate(audios, start=audio_index + 1):
        labels[asset.asset_id] = f"<Audio {index}>"
    return labels


def build_prompt(
    storyboard: Storyboard,
    chunk: ChunkSpec,
    assets: Sequence[Asset],
    *,
    has_tail: bool,
    tail_has_audio: bool = False,
    video_audio_ids: set[str] | None = None,
) -> str:
    """构造确定性的六段式 full-reference prompt。"""

    labels = _reference_labels(
        assets,
        has_tail,
        tail_has_audio=tail_has_audio,
        video_audio_ids=video_audio_ids,
    )
    definitions = [
        f"{labels[asset.asset_id]} is {asset.description}." for asset in assets
    ]
    if has_tail:
        definitions.insert(
            0,
            "<Video 1> is the motion and appearance continuation reference containing the tail of the previous generated window.",
        )

    continuity_lines = [f"Overall visual direction: {storyboard.global_prompt}"]
    for key in ("characters", "environment", "lighting", "camera", "color", "audio"):
        if key in storyboard.continuity:
            continuity_lines.append(f"{key}: {storyboard.continuity[key]}")

    body: list[str] = []
    for shot_index, shot in enumerate(storyboard.shots, start=1):
        if not _intersects(chunk.start_s, chunk.end_s, shot.start_s, shot.end_s):
            continue
        relative_start = max(0.0, shot.start_s - chunk.start_s)
        relative_end = min(chunk.chunk_s, shot.end_s - chunk.start_s)
        shot_assets = [labels[value] for value in shot.asset_ids if value in labels]
        references = f" References: {', '.join(shot_assets)}." if shot_assets else ""
        overlap_note = ""
        if has_tail and relative_start < chunk.overlap_s:
            overlap_note = (
                f" During the first {chunk.overlap_s:.3f} seconds, continue only the "
                "visual and ambient state from <Video 1>; delay any new dialogue or "
                "major action beat until after the transition."
            )
        body.append(
            f"[Shot {shot_index}] At {_format_clock(relative_start)}, continue until "
            f"{_format_clock(relative_end)}. {shot.prompt}{overlap_note}{references}"
        )

    if has_tail:
        transition = (
            f"The first {chunk.overlap_s:.3f} seconds are continuation context from <Video 1>. "
            "Preserve the subject identity, scene geometry, screen direction, lighting, "
            "color grade, and camera motion from that reference. Do not introduce a new "
            "dialogue line or major story beat inside this transition interval."
        )
    else:
        transition = (
            "This is the first window. Establish the persistent characters, environment, "
            "lighting, color grade, and camera language before executing the local shots."
        )

    prompt = "\n\n".join(
        [
            "subject_definitions:\n" + "\n".join(definitions),
            "summary:\n"
            f"[60-second storyboard continuation] Generate target window "
            f"{_format_clock(chunk.start_s)} to {_format_clock(chunk.end_s)} at 24 FPS. "
            "Use only the supplied references for identity, appearance, motion, and sound relationships.",
            "retention_analysis:\n" + "\n".join(continuity_lines) + "\n" + transition,
            "detailed_description:\n"
            + f"The output is cinematic and temporally coherent within this {chunk.chunk_s:.3f}-second window.\n"
            + "\n".join(body),
            "overall_soundscape:\n"
            + storyboard.continuity.get(
                "audio",
                "Maintain natural ambience and preserve the described dialogue timing without adding unrelated voices.",
            ),
            "non_diegetic_music:\n"
            + storyboard.continuity.get(
                "music",
                "Use a restrained score consistent with the global style; do not change its mood abruptly at the window boundary.",
            ),
        ]
    )
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ConfigurationError(
            f"chunk {chunk.index + 1} prompt 长度为 {len(prompt)}，超过 {MAX_PROMPT_CHARS} 字符；"
            "请缩短 shot 描述或接入 Context-IR"
        )
    return prompt


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
