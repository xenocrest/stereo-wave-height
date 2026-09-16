"""Coordinate conversion regression; no WASS executions."""
import importlib.util
from pathlib import Path
import cv2
import numpy as np

spec = importlib.util.spec_from_file_location('canonical', Path(__file__).resolve().parents[1]/'tools/vieira_canonical_intrinsics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_projection_equivariance():
    k = np.array([[1400., 0, 990.], [0, 1380., 510.], [0, 0, 1.]])
    d = np.array([.01, -.02, .003, -.004, .001])
    points = np.array([[.2, .1, 2.], [-.4, .3, 3.], [.1, -.2, 1.5]])
    kc, dc = module.convert(k, d, 1920, 1080)
    observed = cv2.projectPoints(points, np.zeros(3), np.zeros(3), k, d)[0].reshape(-1, 2)
    expected = np.array([1919., 1079.]) - observed
    transformed = points @ np.diag([-1., -1., 1.])
    actual = cv2.projectPoints(transformed, np.zeros(3), np.zeros(3), kc, dc)[0].reshape(-1, 2)
    np.testing.assert_allclose(actual, expected, atol=1e-9)
    np.testing.assert_array_equal(d, [.01, -.02, .003, -.004, .001])
