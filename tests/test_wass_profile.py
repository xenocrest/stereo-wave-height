"""Tests for WASS performance profile parsing and aggregation."""

import unittest

from src.performance.wass_profile import aggregate_profiles, parse_stereo_internal_timing


class WassProfileTests(unittest.TestCase):
    def test_confirmed_timing_table_is_parsed(self) -> None:
        labels = ["Data load", "Rectification", "Dense Stereo", "Triangulation", "Z-gap stats", "Outlier removal", "Plane fitting", "Plane refinement", "TOTAL"]
        text = "\n".join(f"| {label:>24} | {index + 0.25} |" for index, label in enumerate(labels))
        result = parse_stereo_internal_timing(text)
        self.assertEqual(result.data_load_seconds, 0.25)
        self.assertEqual(result.outlier_removal_seconds, 5.25)
        self.assertEqual(result.total_seconds, 8.25)

    def test_missing_timing_fails(self) -> None:
        with self.assertRaises(ValueError):
            parse_stereo_internal_timing("no timing table")

    def test_aggregate_reports_mean_min_max(self) -> None:
        result = aggregate_profiles([{"prepare": 1.0, "match": 3.0}, {"prepare": 2.0, "match": 5.0}])
        self.assertEqual(result["prepare"], {"mean": 1.5, "minimum": 1.0, "maximum": 2.0})
        self.assertEqual(result["match"]["maximum"], 5.0)


if __name__ == "__main__":
    unittest.main()
