"""Small physical/algebra regressions for isolated refraction diagnostics."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from hometank006_refraction_probe import bottom_intersections
from hometank006_refractive_height_probe import snell_normal, sample, air_water_entry_valid
from hometank006_photometric_refraction import project_static_bottom, refract_bottom, sample as continuous_sample


def test_normal_incidence_reaches_bottom_not_water():
    p = bottom_intersections(np.array([[0.,0.,1.]]), np.zeros(3),
                             np.array([0.,0.,-1.]), .4, .1)
    np.testing.assert_allclose(p, [[0,0,.5]], atol=1e-12)


def test_snell_law_and_normal_consistency():
    n = np.array([0.,0.,-1.])
    theta = np.deg2rad(40)
    v = np.array([[np.sin(theta),0,np.cos(theta)]])
    p = bottom_intersections(v, np.zeros(3), n, .4, .1)
    q = .4/v[0,2]*v
    w = (p-q)/np.linalg.norm(p-q,axis=1)[:,None]
    np.testing.assert_allclose(1.333*w[0,0], np.sin(theta), atol=1e-12)
    np.testing.assert_allclose(snell_normal(v,w)[0], n, atol=1e-12)


def test_away_ray_rejected_and_input_immutable():
    v = np.array([[0.,0.,-1.]])
    original = v.copy()
    assert np.isnan(bottom_intersections(v,np.zeros(3),np.array([0.,0.,-1.]),.4,.1)).all()
    np.testing.assert_array_equal(v, original)


def test_remap_more_than_short_max_queries():
    im = np.arange(100,dtype=np.float32).reshape(10,10)
    uv = np.tile([4.,5.],(40000,1))
    np.testing.assert_array_equal(sample(im,uv),np.full((40000,1),54.))


def test_nonzero_surface_height_uses_water_intersection_not_bottom():
    n = np.array([0.,0.,-1.]); c=.4; depth=.1
    for height in [-.01,.01]:
        Q = np.array([.04,.02,c-height])
        normals=[]
        for C in [np.zeros(3),np.array([.1,0,0])]:
            v=(Q-C)/np.linalg.norm(Q-C)
            bottom=bottom_intersections(v[None],C,n,c-height,depth+height)[0]
            water=(bottom-Q)/np.linalg.norm(bottom-Q)
            normals.append(snell_normal(v,water))
            np.testing.assert_allclose(n@Q+c,height,atol=1e-12)
            # Same fixed bottom for BOTH heights: not mistaken for water surface.
            np.testing.assert_allclose(n@bottom+c+depth,0,atol=1e-12)
        np.testing.assert_allclose(normals,[n,n],atol=1e-12)


def test_snell_nonphysical_air_exit_branch_rejected():
    air=np.array([0.,0.,1.])
    water=np.array([np.sin(np.pi/3),0.,np.cos(np.pi/3)])
    n=snell_normal(air,water)
    # The tangential equality is satisfied algebraically but air points out.
    np.testing.assert_allclose(np.cross(n,air-1.333*water),0,atol=1e-12)
    assert not air_water_entry_valid(air,water,n)
    assert air_water_entry_valid(air,air,np.array([0.,0.,-1.]))


def test_static_refraction_inverse_pixel_roundtrip():
    K=np.array([[500.,0,300],[0,500,200],[0,0,1]])
    C=np.array([.1,0,0]);n=np.array([0.,0.,-1.])
    uv=np.array([[200.,180.],[300.,200.],[450.,280.]])
    v=np.column_stack([uv,np.ones(len(uv))])@np.linalg.inv(K).T
    v/=np.linalg.norm(v,axis=1)[:,None]
    bottom=bottom_intersections(v,C,n,.4,.105)
    recovered=project_static_bottom(bottom,C,K,n,.4,.105)
    np.testing.assert_allclose(recovered,uv,atol=1e-7)


def test_tilted_dynamic_plane_keeps_fixed_bottom():
    n=np.array([0.,0.,-1.]);N=np.array([.1,0.,-1.]);N/=np.linalg.norm(N)
    P=np.array([0.,0.,.39]);v=np.array([[0.,0.,1.],[.1,0.,1.]])
    v/=np.linalg.norm(v,axis=1)[:,None]
    E,B,valid=refract_bottom(v,np.zeros(3),N,P,n,.4,.105)
    assert valid.all()
    np.testing.assert_allclose((E-P)@N,0,atol=1e-12)
    np.testing.assert_allclose(B@n+.4+.105,0,atol=1e-12)


def test_photometric_sampler_has_subpixel_continuity():
    y,x=np.indices((20,20));im=.1*x+.01*y
    uv=np.array([[5.21,7.32],[5.210001,7.32]])
    values=continuous_sample(im,uv)[:,0]
    np.testing.assert_allclose(values[1]-values[0],1e-7,atol=1e-12)
