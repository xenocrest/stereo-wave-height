"""General stereo-video input tests with no codec dependency."""

from pathlib import Path
import tempfile
import unittest

import numpy as np

from input import StereoVideoSource, VideoMetadata


class FakeBackend:
    def probe(self, path: Path) -> VideoMetadata:
        return VideoMetadata(path.resolve(), 1920, 1080, 10, 25.0, .4, "test_fixture_fps_index")

    def read_frame(self, path: Path, frame_index: int):
        return np.full((2, 3), frame_index, dtype=np.uint8)


class StereoVideoSourceTests(unittest.TestCase):
    def test_metadata_and_explicit_frame_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left.mp4"; right = Path(directory) / "right.mp4"
            left.touch(); right.touch()
            source = StereoVideoSource(left, right, backend=FakeBackend())
            pair = source.frame_pair(3, 2, 4)
            self.assertEqual((source.left.width_px, source.left.height_px), (1920, 1080))
            self.assertEqual((pair.left_index, pair.right_index), (2, 4))
            self.assertAlmostEqual(pair.left_timestamp_s, .08)
            self.assertAlmostEqual(pair.right_timestamp_s, .16)
            np.testing.assert_array_equal(pair.left_frame, np.full((2, 3), 2))

    def test_out_of_range_frame_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left.mp4"; right = Path(directory) / "right.mp4"
            left.touch(); right.touch()
            source = StereoVideoSource(left, right, backend=FakeBackend())
            with self.assertRaises(IndexError):
                source.frame_pair(0, 10, 0)


if __name__ == "__main__":
    unittest.main()
