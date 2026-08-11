"""Schema-level tests for the confirmed WASS compressed point-cloud loader."""

from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from adapters.wass.output.xyzc import align_wass_points_to_plane, read_wass_xyzc


class WassXyzcTests(unittest.TestCase):
    def test_decode_confirmed_binary_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mesh_cam.xyzC"
            limits = np.array([2.0, 4.0, 8.0, 1.0, 2.0, 3.0], dtype="<f8")
            rotation_inverse_file_order = np.eye(3, dtype="<f8").T.ravel()
            translation = np.array([0.5, -0.5, 1.0], dtype="<f8")
            quantized = np.array([[2, 4, 8], [4, 8, 16]], dtype="<u2").ravel()
            path.write_bytes(
                struct.pack("<I", 2) + limits.tobytes() + rotation_inverse_file_order.tobytes()
                + translation.tobytes() + quantized.tobytes()
            )
            cloud = read_wass_xyzc(path)
            np.testing.assert_allclose(cloud.points_camera, [[2.5, 2.5, 5.0], [3.5, 3.5, 6.0]])

    def test_plane_alignment_and_explicit_scale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mesh_cam.xyzC"
            limits = np.ones(6, dtype="<f8")
            limits[3:] = 0.0
            path.write_bytes(
                struct.pack("<I", 1) + limits.tobytes() + np.eye(3, dtype="<f8").T.ravel().tobytes()
                + np.zeros(3, dtype="<f8").tobytes() + np.array([0, 0, 10], dtype="<u2").tobytes()
            )
            cloud = read_wass_xyzc(path)
            aligned = align_wass_points_to_plane(
                cloud, [0.0, 0.0, 1.0, -10.0], metres_per_baseline_unit=0.2
            )
            np.testing.assert_allclose(aligned, [[0.0, 0.0, 0.0]])

    def test_scale_must_be_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mesh_cam.xyzC"
            path.write_bytes(
                struct.pack("<I", 0) + np.ones(6, dtype="<f8").tobytes()
                + np.eye(3, dtype="<f8").T.ravel().tobytes() + np.zeros(3, dtype="<f8").tobytes()
            )
            cloud = read_wass_xyzc(path)
            with self.assertRaisesRegex(ValueError, "explicitly positive"):
                align_wass_points_to_plane(cloud, [0, 0, 1, 0], metres_per_baseline_unit=0.0)


if __name__ == "__main__":
    unittest.main()
