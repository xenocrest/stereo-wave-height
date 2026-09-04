"""Synthetic water-surface continuity tests; not real sea accuracy claims."""
import numpy as np
import pytest
import yaml
from reconstruction.ocean_surface import OceanSurfacePolicy, complete_water_surface
from reconstruction.dense_height_solver import DenseHeightPolicy


def scene():
    y,x=np.mgrid[0:32,0:40].astype(float);x/=39;y/=31
    h=.015*np.sin(2*np.pi*x)+.004*y
    roi=np.ones(h.shape,bool);obs=(np.indices(h.shape).sum(0)%2)==0
    return h,obs,roi,x,y


def test_wave_trend_complete_and_exact_anchors():
    h,obs,roi,x,y=scene();before=obs.copy()
    result=complete_water_surface(h,obs,roi,roi,x,y,observation_subject="WATER_SURFACE",
        policy=OceanSurfacePolicy(.4,DenseHeightPolicy(gradient_weight=0,curvature_weight=1e-8,anchor_mode="hard")))
    np.testing.assert_array_equal(obs,before)
    np.testing.assert_array_equal(result.height_m[obs],h[obs])
    assert np.isfinite(result.height_m).all()
    assert np.sqrt(np.mean((result.height_m-h)**2))<.001
    assert np.corrcoef(result.height_m.ravel(),h.ravel())[0,1]>.99


def test_reject_bottom_and_sparse_support():
    h,obs,roi,x,y=scene()
    with pytest.raises(ValueError,match="NOT_BOTTOM"):
        complete_water_surface(h,obs,roi,roi,x,y,observation_subject="BOTTOM",policy=OceanSurfacePolicy(.4))
    with pytest.raises(ValueError,match="BELOW_GATE"):
        complete_water_surface(h,obs,roi,roi,x,y,observation_subject="WATER_SURFACE",policy=OceanSurfacePolicy(.8))


def test_pixel_domain_not_stretched_and_nan_not_observation():
    h,obs,roi,x,y=scene();common=roi.copy();common[:,:5]=False
    result=complete_water_surface(h,obs,roi,common,x,y,observation_subject="WATER_SURFACE",policy=OceanSurfacePolicy(.4))
    assert np.isnan(result.height_m[:,:5]).all()
    assert np.isfinite(result.height_m[:,5:]).all()
    h[:]=np.nan
    with pytest.raises(ValueError,match="BELOW_GATE"):
        complete_water_surface(h,obs,roi,common,x,y,observation_subject="WATER_SURFACE",policy=OceanSurfacePolicy(.4))


def test_existing_dense_artifact_pipeline_ocean_mode(tmp_path):
    from surface_completion.dense_map import build_dense_map
    h,obs,roi,x,y=scene();yy,xx=np.indices(h.shape)
    depth=1+h[obs]
    points=np.column_stack((xx[obs]*depth/100,yy[obs]*depth/100,depth))
    np.savez(tmp_path/'points.npz',xyz_m=points,u_px=xx[obs],v_px=yy[obs],pixel_coordinate_system='synthetic_rectified')
    np.savez(tmp_path/'height.npz',height_m=h[obs],water_mask=np.ones(obs.sum(),bool))
    common=roi.copy();common[:,:5]=False
    np.savez(tmp_path/'common.npz',safe_common_mask=common)
    K=np.diag([100.,100.,1.]);P=np.column_stack((K,np.zeros(3)))
    np.savetxt(tmp_path/'P.txt',P)
    mapping={'image_size_px':[40,32],'prepare_undistortion':{'K1':K.tolist(),'D1':[0]*5},
             'stereo_rectification':{'R_computational_cam0':np.eye(3).tolist(),'P_computational_cam0':P.tolist()}}
    (tmp_path/'mapping.yaml').write_text(yaml.safe_dump(mapping),encoding='utf-8')
    config={'frozen':{'pixel_xyz_npz':str(tmp_path/'points.npz'),'height_npz':str(tmp_path/'height.npz'),
        'mapping_yaml':str(tmp_path/'mapping.yaml'),'reference_plane':{'normal':[0,0,1],'offset_m':-1.},
        'projection_txt':str(tmp_path/'P.txt'),'calibrated_baseline_m':.2,'frame_identity':'SYNTHETIC_NOT_WASS_RUN',
        'common_fov_npz':str(tmp_path/'common.npz')},
        'water_roi':{'type':'polygon','coordinate_system':'canonical_cam1','points':[[0,0],[39,0],[39,31],[0,31]]},
        'observation_gate_px':.1,'completion':{'maximum_gap_multiplier':3},
        'mls':{'radius_multiplier':6,'sigma_multiplier':2,'minimum_points':12,'maximum_neighbors':64,'maximum_condition_number':1e8},
        'completion_strategy':'ocean_observation_anchored','observation_subject':'WATER_SURFACE',
        'ocean_policy':{'minimum_observed_ratio':.4},'output_directory':str(tmp_path/'out')}
    result=build_dense_map(config)
    assert result['water_roi_pixel_count']==35*32
    assert result['status']['unsupported']['count']==0
    assert result['metadata']['ocean_completion']['anchor_mode']=='hard'
    domain=result['metadata']['measurement_domain']
    assert domain['requested_roi_pixel_count']==40*32
    assert domain['excluded_non_common_pixel_count']==5*32
    assert domain['evaluation_pixel_count']==35*32
    assert domain['raw_observation_ratio']==.5
    assert domain['finite_model_ratio']==1.
    assert not domain['shrunk_to_observation_support']
    assert result['frozen_artifacts_unchanged']


@pytest.mark.parametrize('roi',[None,{'type':'observed_convex_hull'}])
def test_ocean_requires_preselected_roi_before_loading_artifacts(roi):
    from surface_completion.dense_map import build_dense_map
    config={'completion_strategy':'ocean_observation_anchored'}
    if roi is not None:config['water_roi']=roi
    with pytest.raises(ValueError,match='EXPLICIT_WATER_ROI_REQUIRED'):
        build_dense_map(config)


def test_explicit_roi_does_not_follow_point_support():
    from surface_completion.dense_map import rasterize_water_roi
    roi={'type':'polygon','coordinate_system':'canonical_cam1',
         'points':[[0,0],[39,0],[39,31],[0,31]]}
    masks=[rasterize_water_roi(roi,width=40,height=32,
        observed_rectified_px=points,canonical_rectified_px=np.zeros((1280,2)))
        for points in (np.array([[1.,1.],[2.,1.],[1.,2.]]),
                       np.array([[20.,20.],[35.,20.],[20.,30.]]))]
    np.testing.assert_array_equal(masks[0],masks[1])
    assert masks[0].sum()==1280
