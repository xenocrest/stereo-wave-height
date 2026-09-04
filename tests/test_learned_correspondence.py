"""Geometric adapter checks without model downloads or ML dependencies."""
import numpy as np
import pytest
from reconstruction.learned_correspondence import horizontal_disparity,TorchvisionRaftCorrespondence
from reconstruction.opencv_dense import DenseStereoPolicy,reconstruct_dense_stereo


def test_flow_is_correspondence_not_metric_height():
    flow=np.zeros((2,4,12));flow[0]=-4
    disparity=horizontal_disparity(flow,1.)
    assert np.all(disparity==4)
    flow[1,:,3]=2
    assert np.isnan(horizontal_disparity(flow,1.)[:,3]).all()


def test_external_backend_still_uses_calibrated_metric_reprojection():
    class Backend:
        name='SYNTHETIC_CORRESPONDENCES_TEST_ONLY'
        def compute(self,left,right):return np.full(left.shape[:2],8.),np.full(right.shape[:2],-8.)
    im=np.zeros((96,160),np.uint8);k=np.array([[120.,0,80],[0,120.,48],[0,0,1.]])
    result=reconstruct_dense_stereo(im,im,K0=k,D0=np.zeros(5),K1=k,D1=np.zeros(5),
        R_right_from_left=np.eye(3),T_right_from_left_m=np.array([-.1,0,0]),
        policy=DenseStereoPolicy(num_disparities=32),disparity_backend=Backend())
    assert np.allclose(result.xyz_m[:,:,2][result.valid_mask],1.5)
    assert np.isnan(result.xyz_m[~result.valid_mask]).all()
    assert result.metadata['backend']==Backend.name


def test_vertical_gate_must_be_finite():
    with pytest.raises(ValueError):horizontal_disparity(np.zeros((2,3,4)),float('nan'))


def test_crop_restores_original_pixel_disparity_not_crop_disparity():
    model=object.__new__(TorchvisionRaftCorrespondence)
    model.horizontal_crop_offset_px=32;model.vertical_tolerance_px=1.
    calls=[]
    def flow(a,b):
        output=np.zeros((2,*a.shape[:2]),np.float32);output[0]=-8 if not calls else 8
        calls.append(True);return output
    model._flow=flow
    a=np.zeros((128,192,3),np.uint8);dl,dr=model.compute(a,a)
    assert np.isnan(dl[:,:32]).all() and np.isnan(dr[:,-32:]).all()
    assert np.all(dl[:,32:]==40) and np.all(dr[:,:160]==-40)
    assert np.all(model.last_forward_flow[0,:,32:]==-40)
