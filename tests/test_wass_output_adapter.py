"""Tests for the extensible WASS-output adapter boundary."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from adapters.wass.output.model import StandardizedGrid3D
from adapters.wass.output.parser import WassOutputParser
from adapters.wass.output.simulated import from_standardized_simulation


class _ExampleVersionParser:
    """Test double proving the parser Protocol without parsing WASS."""

    format_id = "test-only"

    def parse(self, source: Path) -> StandardizedGrid3D:
        del source
        return from_standardized_simulation(
            x=[0.0],
            y=[0.0],
            z=[[[1.0]]],
            timestamp_ns=[0],
            valid_mask=[[[True]]],
            coordinate_system="world_water_surface",
            unit="m",
        )


class WassOutputAdapterTests(unittest.TestCase):
    """Verify simulation input validation and parser extensibility."""

    def test_standardized_simulation_factory(self) -> None:
        result = from_standardized_simulation(
            x=[0.0, 1.0],
            y=[0.0],
            z=[[[2.0, np.nan]]],
            timestamp_ns=[10],
            valid_mask=[[[True, False]]],
            coordinate_system="world_water_surface",
            unit="m",
        )
        self.assertEqual(result.z.shape, (1, 1, 2))
        self.assertTrue(np.isnan(result.z[0, 0, 1]))

    def test_version_parser_protocol(self) -> None:
        parser = _ExampleVersionParser()
        self.assertIsInstance(parser, WassOutputParser)
        self.assertEqual(parser.parse(Path("unused")).unit, "m")


if __name__ == "__main__":
    unittest.main()
