"""Small regression checks: changing support must not fake height drift."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from audit_foundationstereo_height_stability import temporal_comparison, statistics


def test_fixed_intersection_excludes_changing_support():
    h=np.array([[0.,1.,2.]])
    result=temporal_comparison([h,h+.01],
        [np.array([[True,True,False]]),np.array([[False,True,True]])],
        np.ones(h.shape,bool))
    assert result['common_pixels']==1
    assert np.isclose(result['relative_to_first'][1]['mean_mm'],10)


def test_no_common_support_has_no_fabricated_metric():
    h=np.zeros((1,2))
    result=temporal_comparison([h,h],[np.array([[True,False]]),
        np.array([[False,True]])],np.ones(h.shape,bool))
    assert result['common_pixels']==0
    assert result['relative_to_first'][1]['rms_mm'] is None


def test_diagnostic_does_not_modify_input_arrays():
    h=np.arange(4.,dtype=float).reshape(2,2)
    original=h.copy(); m=np.ones(h.shape,bool)
    temporal_comparison([h,h],[m,m],m)
    statistics(h)
    assert np.array_equal(original,h)
    assert m.all()
