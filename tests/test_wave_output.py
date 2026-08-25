"""Tests for stable wave CSV/JSON output contracts."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from src.validation.wave_output import build_wave_frame_record, write_wave_result_json, write_wave_timeseries_csv


class WaveOutputTests(unittest.TestCase):
    def test_record_contains_complete_height_statistics(self) -> None:
        record = build_wave_frame_record("000001", 10, np.asarray([-1.0, 0.0, 1.0]))
        self.assertEqual(record.valid_points, 3)
        self.assertEqual(record.median_H_m, 0.0)
        self.assertEqual(record.rms_H_m, np.sqrt(2.0 / 3.0))

    def test_csv_keeps_raw_and_filtered_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = build_wave_frame_record("000001", 10, np.asarray([1.0]))
            path = write_wave_timeseries_csv(
                Path(temporary) / "series.csv", [record], np.asarray([0.5]), np.asarray([0.5])
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("mean_H_m", text)
            self.assertIn("low_frequency_baseline_m", text)
            self.assertIn("filtered_H_m", text)

    def test_json_requires_validation_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            result = {"status": "DONE", "height_series": [], "statistics": {}, "validation_status": "MANUAL_REFERENCE_REQUIRED"}
            write_wave_result_json(path, result)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "DONE")
            with self.assertRaises(ValueError):
                write_wave_result_json(path, {"status": "DONE"})


if __name__ == "__main__":
    unittest.main()
