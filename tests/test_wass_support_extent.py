import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from validation.wass_support_extent import (
    effective_disparity, read_component_labels, read_precluster_depth, support_funnel,
)


class WassSupportExtentTests(unittest.TestCase):
    def test_observability_binary_readers(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            depth = root / "depth.bin"
            labels = root / "labels.bin"
            with depth.open("wb") as stream:
                stream.write(b"WASSPCZ1" + struct.pack("<II", 2, 1))
                np.asarray([2.0, 4.0], dtype="<f8").tofile(stream)
                np.asarray([1, 0], dtype="u1").tofile(stream)
            with labels.open("wb") as stream:
                stream.write(b"WASSCCL1" + struct.pack("<II", 2, 1))
                np.asarray([7, -1], dtype="<i4").tofile(stream)
            artifact = read_precluster_depth(depth)
            self.assertEqual(artifact.valid.tolist(), [[True, False]])
            self.assertEqual(read_component_labels(labels).tolist(), [[7, -1]])

    def test_effective_disparity_and_funnel_validation(self) -> None:
        np.testing.assert_allclose(effective_disparity([5.0, 10.0], 1000.0), [200.0, 100.0])
        self.assertEqual(support_funnel(100, 40, 30, 29)["final_xyz"], 29)
        with self.assertRaises(ValueError):
            support_funnel(10, 11, 5, 4)


if __name__ == "__main__":
    unittest.main()
