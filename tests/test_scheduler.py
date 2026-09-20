"""测试 H3 帧数对齐和 60 秒窗口契约。"""

import unittest

from minimax_h3_long_video.constants import H3_SAFE_CHUNK_SECONDS
from minimax_h3_long_video.scheduler import align_frame_count, make_chunks


class SchedulerTest(unittest.TestCase):
    """覆盖稳定的离线窗口规划行为。"""

    def test_safe_frame_alignment(self) -> None:
        """确认 15 秒请求不会被错误对齐到非法的 362 帧。"""

        self.assertEqual(align_frame_count(345), 345)
        self.assertEqual(align_frame_count(360), 362)

    def test_default_sixty_second_schedule(self) -> None:
        """确认五个窗口和 overlap 精确覆盖 60 秒。"""

        chunks = make_chunks(60.0)
        self.assertEqual(len(chunks), 5)
        self.assertEqual(chunks[0].num_frames, 345)
        self.assertAlmostEqual(chunks[0].chunk_s, H3_SAFE_CHUNK_SECONDS)
        self.assertAlmostEqual(chunks[-1].end_s, 60.0)
        self.assertAlmostEqual(
            5 * chunks[0].chunk_s - 4 * chunks[1].overlap_s,
            60.0,
        )


if __name__ == "__main__":
    unittest.main()

