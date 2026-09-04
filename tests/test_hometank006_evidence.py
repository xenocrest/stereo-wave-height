import numpy as np
import pytest
from synchronization.audio_sync import lag_seconds
from calibration.board_identity import parity_contrast,register_parity
from reconstruction.opencv_dense import DenseStereoPolicy,disparity_observation_mask


def test_audio_right_minus_left_sign():
    rng=np.random.default_rng(21);x=rng.normal(size=10000)
    y=np.r_[np.zeros(123),x[:-123]]
    assert lag_seconds(x,y,1000,1)==pytest.approx(.123)


def test_silence_does_not_establish_sync():
    with pytest.raises(ValueError):lag_seconds(np.zeros(100),np.zeros(100),1000,1)


def test_parity_registration_only_reorders_observations():
    grid=np.arange(6*9*2).reshape(6,9,2)
    out,flip=register_parity(grid,50,-40)
    assert flip
    assert np.array_equal(out,grid[::-1,::-1])
    assert np.array_equal(grid,np.arange(108).reshape(6,9,2))


def test_unobservable_polarity_rejected():
    with pytest.raises(ValueError):register_parity(np.zeros((6,9,2)),2,50)


def test_measured_cell_polarity():
    yy,xx=np.indices((80,110));image=(((xx//10+yy//10)%2)*180+20).astype(np.uint8)
    x,y=np.meshgrid(np.arange(1,10)*10,np.arange(1,7)*10);grid=np.stack((x,y),axis=-1)
    assert abs(parity_contrast(image,grid))==180


def test_search_endpoint_is_not_a_supported_depth():
    left=np.full((1,32),15.);right=-left
    support=np.ones(left.shape,bool)
    mask,counts=disparity_observation_mask(left,right,support,support,DenseStereoPolicy(num_disparities=16))
    assert not mask.any()
    assert counts['left_search_endpoint_count']==32


def test_corresponding_source_pixel_must_be_observed():
    left=np.full((1,32),4.);right=-left;support=np.ones(left.shape,bool)
    mask,_=disparity_observation_mask(left,right,support,support,DenseStereoPolicy(num_disparities=16))
    assert mask[0,4:].all()
    right_support=support.copy();right_support[0,6]=False
    mask,_=disparity_observation_mask(left,right,support,right_support,DenseStereoPolicy(num_disparities=16))
    assert not mask[0,10]


def test_right_invalid_sentinel_cannot_pass_tolerance():
    # A large tolerance must not turn the matcher sentinel into an observation.
    left=np.full((1,32),14.);right=np.full(left.shape,-16.)
    support=np.ones(left.shape,bool)
    mask,_=disparity_observation_mask(left,right,support,support,
        DenseStereoPolicy(num_disparities=16,left_right_tolerance_px=3))
    assert not mask.any()
