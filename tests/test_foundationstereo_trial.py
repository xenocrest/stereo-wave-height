"""Small mathematical checks for the isolated official-model diagnostic."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('ffs_diagnostic',Path(__file__).parents[1]/'tools/analyze_foundationstereo_trial.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_right_camera_metric_reprojection_and_height():
    q=np.array([[1,0,0,-1],[0,1,0,-1],[0,0,0,100],[0,0,5,0]],dtype=float)
    disparity=np.full((3,3),10,dtype=np.float32)
    points=module.right_camera_points(disparity,q,np.eye(3))
    assert np.allclose(points[...,2],2)
    # Baseline-normalized reference depth 10*0.2=2 m.
    assert np.allclose(module.signed_height(points,np.array([0,0,1,-10]),.2),0)
    points[...,2]-=.01
    assert np.allclose(module.signed_height(points,np.array([0,0,1,-10]),.2),.01)


def test_non_zero_principal_point_offset_rejected():
    with pytest.raises(ValueError):
        module.right_camera_points(np.ones((2,2)),np.eye(4),np.eye(3))


def test_right_origin_agrees_with_opencv_triangulation():
    p0=np.array([[100,0,1,0],[0,100,1,0],[0,0,1,0]],dtype=float)
    p1=p0.copy()
    p1[0,3]=-20
    homogeneous=module.cv2.triangulatePoints(p0,p1,np.array([[11.],[1.]]),np.array([[1.],[1.]]))
    right=(homogeneous[:3,0]/homogeneous[3,0])-np.array([.2,0,0])
    q=np.array([[1,0,0,-1],[0,1,0,-1],[0,0,0,100],[0,0,5,0]],dtype=float)
    result=module.right_camera_points(np.full((3,3),10,dtype=np.float32),q,np.eye(3))
    assert np.allclose(result[1,1],right)
