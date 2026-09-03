import unittest
import numpy as np

from reconstruction.dense_height_solver import DIRECT_STEREO,VARIATIONAL_ESTIMATE,DenseHeightPolicy,solve_dense_height


class DenseHeightSolverTests(unittest.TestCase):
    @staticmethod
    def field():
        y,x=np.mgrid[0:18,0:24];x=x*.002;y=y*.002
        truth=.004+.03*x-.02*y
        roi=np.ones(truth.shape,bool);observed=np.zeros_like(roi);observed[::3,::3]=True
        return x,y,truth,roi,observed

    def test_plane_truth_is_recovered_over_every_roi_pixel(self):
        x,y,truth,roi,observed=self.field()
        result=solve_dense_height(truth,observed,roi,x,y,policy=DenseHeightPolicy(gradient_weight=0,curvature_weight=1e-8))
        self.assertTrue(np.all(np.isfinite(result.height_m[roi])))
        self.assertLess(float(np.sqrt(np.mean((result.height_m[roi]-truth[roi])**2))),2e-5)
        self.assertTrue(np.all(result.source_status[observed]==DIRECT_STEREO))
        self.assertTrue(np.all(result.source_status[roi&~observed]==VARIATIONAL_ESTIMATE))

    def test_unanchored_component_is_rejected(self):
        x,y,truth,roi,observed=self.field();roi[:,11:13]=False;observed[:,13:]=False
        with self.assertRaisesRegex(ValueError,"UNANCHORED"):
            solve_dense_height(truth,observed,roi,x,y)

    def test_insufficient_observations_is_rejected(self):
        x,y,truth,roi,observed=self.field();observed[:]=False;observed[0,0]=True
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT"):
            solve_dense_height(truth,observed,roi,x,y)


if __name__=="__main__":unittest.main()
