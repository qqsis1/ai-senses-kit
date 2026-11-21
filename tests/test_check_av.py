"""check_av 的纯函数测试：不需要 ffmpeg、不需要视频。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_av  # noqa: E402


SAMPLE_SRT = """1
00:00:00,800 --> 00:00:02,400
我把声音关掉了

2
00:00:02,400 --> 00:00:05,280
屋子还在，杯子还在冒气
"""


class SrtParseTest(unittest.TestCase):
    def test_parses_two_cues(self):
        cues = check_av.srt_parse(self._write(SAMPLE_SRT))
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(cues[0]["t0"], 0.8, places=2)
        self.assertAlmostEqual(cues[1]["t1"], 5.28, places=2)
        self.assertIn("杯子", cues[1]["text"])

    def test_coverage_high_for_same_text(self):
        self.assertGreater(check_av.coverage("屋子还在，杯子还在冒气", "屋子还在杯子还在冒气"), 0.9)

    def test_coverage_low_for_unrelated_text(self):
        self.assertLess(check_av.coverage("安静不是没有声音", "今天天气不错我们出去走走"), 0.2)

    @staticmethod
    def _write(text: str) -> str:
        import tempfile
        f = tempfile.NamedTemporaryFile('w', suffix='.srt', delete=False, encoding='utf-8')
        f.write(text)
        f.close()
        return f.name


if __name__ == "__main__":
    unittest.main()
