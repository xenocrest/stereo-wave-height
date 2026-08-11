"""Tests for Case 0 XML/config preparation; real WASS is not run here."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from adapters.wass.input.config_derivation import derive_wass_config
from adapters.wass.input.opencv_xml import inspect_opencv_matrix_schema, write_wass_calibration_xml


class WassCase0InputTests(unittest.TestCase):
    def test_confirmed_opencv_xml_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            files = write_wass_calibration_xml(
                temporary,
                intrinsic_00=np.eye(3), intrinsic_01=np.eye(3),
                distortion_00=np.zeros(5), distortion_01=np.zeros(5),
            )
            schemas = [inspect_opencv_matrix_schema(path) for path in files]
            self.assertEqual([(item.root_tag, item.node_name, item.data_type) for item in schemas],
                             [("opencv_storage", "intrinsics_penne", "d")] * 4)
            self.assertEqual([(item.rows, item.cols) for item in schemas],
                             [(3, 3), (3, 3), (5, 1), (5, 1)])

    def test_config_derivation_changes_only_named_existing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("# comment\n#MIN_DISPARITY=1\n#MAX_DISPARITY=640\n", encoding="utf-8")
            target = derive_wass_config(
                source, root / "target.txt", overrides={"MIN_DISPARITY": 160, "MAX_DISPARITY": 320}
            )
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "# comment\nMIN_DISPARITY=160\nMAX_DISPARITY=320\n",
            )

    def test_config_derivation_rejects_unverified_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.txt"
            source.write_text("#KNOWN=1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "UNKNOWN_KEY"):
                derive_wass_config(source, Path(temporary) / "target.txt", overrides={"UNKNOWN_KEY": 2})


if __name__ == "__main__":
    unittest.main()
