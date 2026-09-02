import unittest
import numpy as np
from src.surface_completion.constrained_full_domain import (
    OBSERVED, ESTIMATED_LOCAL, ESTIMATED_GLOBAL_MODEL,
    apply_verified_sources, fit_constrained_surface,
)


class ConstrainedFullDomainTest(unittest.TestCase):
    def support(self):
        y,x=np.mgrid[0:1:14j,0:1:18j];xy=np.column_stack((x.ravel(),y.ravel()))
        h=.004*x.ravel()-.003*y.ravel()+.001*np.sin(3*x.ravel())
        return xy,h

    def test_full_domain_is_finite_bounded_and_populated(self):
        xy,h=self.support();result=fit_constrained_surface(xy,h,output_shape=(60,80),model_grid_shape=(18,24))
        self.assertTrue(np.all(np.isfinite(result.height_m)))
        self.assertTrue(np.all(result.source_status==ESTIMATED_GLOBAL_MODEL))
        self.assertTrue(np.all(result.confidence>0))
        self.assertLess(result.height_m.max()-result.height_m.min(),.05)

    def test_observed_overrides_local_and_global(self):
        xy,h=self.support();result=fit_constrained_surface(xy,h,output_shape=(20,30),model_grid_shape=(10,15))
        observed=np.zeros((20,30),bool);local=observed.copy();observed[5,5]=True;local[5,5]=True;local[8,8]=True
        observed_h=np.zeros((20,30));observed_h[5,5]=.123;local_h=np.zeros((20,30));local_h[5,5]=.2;local_h[8,8]=.04
        merged=apply_verified_sources(result,observed,observed_h,local,local_h)
        self.assertEqual(merged.source_status[5,5],OBSERVED);self.assertEqual(merged.height_m[5,5],.123)
        self.assertEqual(merged.source_status[8,8],ESTIMATED_LOCAL)

    def test_degenerate_support_fails_explicitly(self):
        x=np.linspace(0,1,20);xy=np.column_stack((x,x))
        with self.assertRaisesRegex(ValueError,"NOT_IDENTIFIABLE"):
            fit_constrained_surface(xy,x,output_shape=(10,10))


if __name__ == "__main__": unittest.main()
