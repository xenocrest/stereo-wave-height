import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adapters.wass.rectification_policy import (
    CANDIDATE_A_POLICY_MATRIX,
    CALIB_ZERO_DISPARITY,
    ProductionWassRectificationCapability,
    RectificationPolicy,
)


class WassRectificationPolicyTests(unittest.TestCase):
    def test_candidate_a_matrix_is_exact_and_production_rejects_every_entry(self):
        self.assertEqual(
            [(p.test_id, p.alpha, p.zero_disparity) for p in CANDIDATE_A_POLICY_MATRIX],
            [("A0", 0.0, True), ("A1", 0.5, True), ("A2", 1.0, True), ("A3", 0.0, False)],
        )
        capability = ProductionWassRectificationCapability()
        for policy in CANDIDATE_A_POLICY_MATRIX:
            self.assertFalse(capability.supports(policy))
            with self.assertRaisesRegex(RuntimeError, "unsupported by the production WASS"):
                capability.require_supported(policy)

    def test_compiled_policy_is_recognized_without_changing_calibration(self):
        capability = ProductionWassRectificationCapability()
        compiled = RectificationPolicy(1.0, False, "PRODUCTION_COMPILED")
        self.assertTrue(capability.supports(compiled))

    def test_default_policy_preserves_compiled_behavior(self):
        policy = RectificationPolicy()
        self.assertEqual(policy.alpha, 1.0)
        self.assertFalse(policy.zero_disparity)
        self.assertEqual(policy.flags, 0)
        self.assertEqual(
            policy.wass_config_lines(),
            ("RECTIFICATION_ALPHA=1", "RECTIFICATION_ZERO_DISPARITY=false"),
        )

    def test_zero_disparity_maps_to_opencv_flag(self):
        policy = RectificationPolicy(alpha=0.0, zero_disparity=True)
        self.assertEqual(policy.flags, CALIB_ZERO_DISPARITY)
        self.assertEqual(
            policy.wass_config_lines(),
            ("RECTIFICATION_ALPHA=0", "RECTIFICATION_ZERO_DISPARITY=true"),
        )

    def test_experiment_yaml_parsing(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "policy.yaml"
            path.write_text(
                "candidate: FULL_CALIBRATION\n"
                "rectification:\n"
                "  alpha: 0.0\n"
                "  zero_disparity: true\n"
                "source: CONTROLLED_EXPERIMENT\n",
                encoding="utf-8",
            )
            policy = RectificationPolicy.from_yaml(path)
        self.assertEqual((policy.alpha, policy.zero_disparity, policy.flags), (0.0, True, 1024))


if __name__ == "__main__":
    unittest.main()
