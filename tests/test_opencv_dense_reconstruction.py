import unittest
import numpy as np

from reconstruction.opencv_dense import DenseStereoPolicy,left_right_consistency,reconstruct_dense_stereo


class OpenCvDenseReconstructionTests(unittest.TestCase):
    def test_policy_rejects_non_opencv_disparity_multiple(self):
        with self.assertRaises(ValueError):DenseStereoPolicy(num_disparities=30)

    def test_left_right_consistency_uses_opposite_signed_right_disparity(self):
        left=np.full((3,12),2.0);right=np.full((3,12),-2.0)
        mask=left_right_consistency(left,right,0.1)
        self.assertTrue(np.all(mask[:,2:]));self.assertFalse(np.any(mask[:,:2]))

    def test_parallel_calibration_returns_metric_xyz_and_explicit_mask(self):
        rng=np.random.default_rng(7);left=rng.integers(0,256,(96,160),dtype=np.uint8)
        disparity=8;right=np.zeros_like(left);right[:,:-disparity]=left[:,disparity:]
        k=np.array([[120.,0.,80.],[0.,120.,48.],[0.,0.,1.]])
        result=reconstruct_dense_stereo(left,right,K0=k,D0=np.zeros(5),K1=k,D1=np.zeros(5),
            R_right_from_left=np.eye(3),T_right_from_left_m=np.array([-.1,0.,0.]),
            policy=DenseStereoPolicy(num_disparities=32,block_size=5,uniqueness_ratio=0,speckle_window_size=0))
        self.assertEqual(result.xyz_m.shape,(96,160,3));self.assertEqual(result.valid_mask.shape,(96,160))
        self.assertEqual(result.metadata["xyz_unit"],"m");self.assertGreater(result.metadata["valid_count"],0)
        depth=result.xyz_m[...,2][result.valid_mask]
        self.assertTrue(np.all(np.isfinite(depth)))


if __name__=="__main__":unittest.main()
