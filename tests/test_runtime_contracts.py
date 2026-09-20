"""测试音频参考标签、输入契约和恢复指纹。"""

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from minimax_h3_long_video.media_probe import has_audio_stream
from minimax_h3_long_video.prompting import _reference_labels
from minimax_h3_long_video.references import build_references
from minimax_h3_long_video.runner import RunConfig, _run_fingerprint
from minimax_h3_long_video.scheduler import make_chunks
from minimax_h3_long_video.schemas import Asset
from minimax_h3_long_video.storyboard import load_storyboard


class RuntimeContractsTest(unittest.TestCase):
    """覆盖不依赖模型权重的运行时契约。"""

    def test_audio_labels_follow_h3_reference_order(self) -> None:
        """确认视频音轨占用独立的 Audio 标签序号。"""

        assets = (
            Asset("clip", "video", Path("clip.mp4"), "persistent", "motion clip"),
            Asset("voice", "audio", Path("voice.wav"), "persistent", "voice reference"),
        )
        labels = _reference_labels(
            assets,
            has_tail=True,
            tail_has_audio=True,
            video_audio_ids={"clip"},
        )
        self.assertEqual(labels["clip"], "<Video 2>")
        self.assertEqual(labels["voice"], "<Audio 3>")

    def test_audio_only_reference_is_rejected(self) -> None:
        """确认 audio-only 请求在导入 Diffusers 前失败。"""

        audio = Asset("voice", "audio", Path("voice.wav"), "persistent", "voice")
        with self.assertRaisesRegex(ValueError, "不能单独使用"):
            build_references((audio,), None)

    @patch("minimax_h3_long_video.references.media_duration", return_value=1.0)
    def test_short_audio_reference_is_rejected(self, _media_duration: object) -> None:
        """确认单个过短音频在模型调用前失败。"""

        image = Asset("subject", "image", Path("subject.png"), "persistent", "subject")
        audio = Asset("voice", "audio", Path("voice.wav"), "persistent", "voice")
        with self.assertRaisesRegex(ValueError, "不在 2–15s 范围内"):
            build_references((image, audio), None)

    @patch(
        "minimax_h3_long_video.media_probe.probe_media",
        return_value={"streams": [{"codec_type": "video"}, {"codec_type": "audio"}]},
    )
    def test_has_audio_stream_uses_stream_type(self, _probe_media: object) -> None:
        """确认音轨判断只依赖 ffprobe 的 codec_type。"""

        self.assertTrue(has_audio_stream(Path("clip.mp4")))

    def test_run_fingerprint_changes_with_seed(self) -> None:
        """确认改变 seed 后不能复用旧运行。"""

        root = Path(__file__).resolve().parents[1]
        storyboard_path = root / "configs" / "storyboard.example.json"
        storyboard = load_storyboard(storyboard_path, require_paths=False)
        chunks = make_chunks(storyboard.duration_s)
        config = RunConfig(
            storyboard_path=storyboard_path,
            output_dir=root / "outputs" / "test-runtime-contracts",
            dry_run=True,
        )
        changed = replace(config, seed=config.seed + 1)
        self.assertNotEqual(
            _run_fingerprint(storyboard, chunks, config),
            _run_fingerprint(storyboard, chunks, changed),
        )


if __name__ == "__main__":
    unittest.main()
