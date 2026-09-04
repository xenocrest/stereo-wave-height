"""No WASS execution: diagnostic parser and camera convention checks."""
import numpy as np
from wass_fixed_roi_batch import parse_counts, project_input_right


def test_stage_counts_do_not_invent_missing_data():
    counts=parse_counts('triangulate [info ] 316823 valid points found\ncluster [info ] biggest component: 804 size: 60660 (px)')
    assert counts['valid_triangulated_points']==316823
    assert counts['largest_component_points']==60660
    assert counts['filtered_points'] is None
    assert parse_counts('rectification failed')['valid_triangulated_points'] is None


def test_canonical_right_projection_uses_actual_computational_camera():
    g={'K1':np.diag([100.,100.,1.]),'D1':np.zeros(5),
       'R':np.eye(3),'T_m':[[-.2],[0],[0]]}
    points=np.array([[1.,2.,10.]])
    np.testing.assert_allclose(project_input_right(points,g,True),[[10,20]])
    np.testing.assert_allclose(project_input_right(points,g,False),[[0,20]])
    np.testing.assert_array_equal(points,[[1,2,10]])
