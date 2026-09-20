"""测试示例 storyboard 的结构化校验。"""

import unittest
from pathlib import Path

from minimax_h3_long_video.storyboard import load_storyboard


class StoryboardTest(unittest.TestCase):
    """确认公开示例可以在无资产文件时完成干跑解析。"""

    def test_example_storyboard(self) -> None:
        """确认时间轴、帧率和资产引用均有效。"""

        root = Path(__file__).resolve().parents[1]
        storyboard = load_storyboard(
            root / "configs" / "storyboard.example.json",
            require_paths=False,
        )
        self.assertEqual(storyboard.duration_s, 60.0)
        self.assertEqual(storyboard.fps, 24)
        self.assertEqual(len(storyboard.shots), 6)
        self.assertEqual(storyboard.shots[-1].end_s, 60.0)


if __name__ == "__main__":
    unittest.main()

