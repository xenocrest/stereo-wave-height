"""Model-independent compatibility and read-only integration checks."""
from copy import deepcopy
import numpy as np
import pytest
from reconstruction.foundation_demo import identity, compatible
from reconstruction.reference_frame import roi_identity
from application.foundation_runtime import load_runtime


def calibration():
    return {'camera_left':{'K':np.eye(3).tolist(),'D':[0]*5},
        'camera_right':{'K':np.eye(3).tolist(),'D':[0]*5},
        'stereo':{'R':np.eye(3).tolist(),'T_m':[-.1,0,0]}}


def test_geometry_not_display_name():
    a=calibration();b=deepcopy(a);b['calibration_id']='another display name'
    assert identity(a,{'left':180,'right':0},(1920,1080))==identity(b,{'left':180,'right':0},(1920,1080))


def test_reference_rejects_changed_geometry_or_roi():
    a=identity(calibration(),{'left':180,'right':0},(1920,1080));roi={'points':[[0,0],[1,1],[0,1]]}
    ref={'foundation_identity':a,'video_pair_id':'pair','roi_id':roi_identity(roi)}
    compatible(ref,a,'pair',roi)
    with pytest.raises(ValueError):compatible(ref,a,'different_pair',roi)
    changed=deepcopy(a);changed['rotations']['left']=0
    with pytest.raises(ValueError):compatible(ref,changed,'pair',roi)
    with pytest.raises(ValueError):compatible(ref,a,'pair',{'points':[]})


def test_runtime_absent_keeps_legacy(tmp_path,monkeypatch):
    monkeypatch.delenv('STEREO_FOUNDATION_RUNTIME',raising=False)
    assert load_runtime(tmp_path) is None
