"""Physical intersection and analytic-normal tests, not empirical accuracy."""
import numpy as np
import pytest
from reconstruction.refractive_surface import QuadraticWaterSurface


def model(a):
    return QuadraticWaterSurface(np.array([0.,0,-1]),.4,np.array([0.,0,.4]),
                                 np.array([1.,0,0]),np.array([0.,1,0]),.1,np.array(a,float))


def test_constant_positive_height_and_away_ray():
    P,N,H,ok=model([.1,0,0,0,0,0]).intersect(np.zeros(3),np.array([[0.,0,1],[0.,0,-1]]))
    assert ok.tolist()==[True,False]
    np.testing.assert_allclose(P[0],[0,0,.39],atol=1e-12)
    np.testing.assert_allclose(H[0],.01,atol=1e-12)
    assert np.isnan(P[1]).all()


def test_quadratic_ray_hits_obey_surface_equation():
    s=model([.03,.02,-.01,.08,-.03,.04]);v=np.array([[.05,.02,1.],[-.04,.03,1.]])
    P,N,H,valid=s.intersect(np.zeros(3),v)
    assert valid.all()
    np.testing.assert_allclose(P@s.normal+s.offset_m,H,atol=1e-11)
    np.testing.assert_allclose(np.linalg.norm(N,axis=1),1,atol=1e-12)


def test_analytic_normal_is_integrable_gradient():
    s=model([.03,.02,-.01,.08,-.03,.04]);p=np.array([[.01,.02,.4]])
    h,N=s.height_and_normal(p);eps=1e-6
    gx=(s.height_and_normal(p+eps*s.e1)[0]-s.height_and_normal(p-eps*s.e1)[0])/(2*eps)
    gy=(s.height_and_normal(p+eps*s.e2)[0]-s.height_and_normal(p-eps*s.e2)[0])/(2*eps)
    expected=s.normal-gx[:,None]*s.e1-gy[:,None]*s.e2;expected/=np.linalg.norm(expected,axis=1)[:,None]
    np.testing.assert_allclose(N,expected,atol=1e-10)


def test_unknown_geometry_is_rejected():
    with pytest.raises(ValueError):model([np.nan,0,0,0,0,0])
