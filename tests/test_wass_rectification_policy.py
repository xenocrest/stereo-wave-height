import unittest

from adapters.wass.rectification_policy import (
    CANDIDATE_A_POLICY_MATRIX,
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
        compiled = RectificationPolicy("PRODUCTION_COMPILED", 1.0, False)
        self.assertTrue(capability.supports(compiled))


if __name__ == "__main__":
    unittest.main()
