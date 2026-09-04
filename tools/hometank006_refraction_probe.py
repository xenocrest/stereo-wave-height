"""Static flat-interface Snell-law hypothesis test; never emits water heights.

Parallel planar bottom is a user-specified modeling assumption, not a test gate.
Water index is an explicit ideal approximation, not a measurement.
Input is saved bidirectional *2-D* correspondence, not zeroed vertical disparity.
Fits and hold-outs assess this hypothesis, not independent physical accuracy.
"""
from pathlib import Path
import hashlib
import json
import cv2
import numpy as np
from scipy.optimize import least_squares

ROOT = Path('D:/stereo-wave-height-runs/HomeTank_006')


def bottom_intersections(rays, center, normal, offset, depth, index=1.333):
    """Air ray -> water entry -> parallel bottom, all distances in meters.

    n points from water to air; water: n.X+c=0; bottom: n.X+c+d=0.
    Returns NaN for a ray not crossing the interface in its forward direction.
    """
    nv = rays @ normal
    entry_t = -(center @ normal + offset) / nv
    eta = 1.0 / index
    cos_i = -nv
    cos_t = np.sqrt(1 - eta**2 * (1 - cos_i**2))
    transmitted = eta * rays + (eta*cos_i-cos_t)[:, None]*normal
    entry = center + entry_t[:, None]*rays
    points = entry - (depth / (transmitted @ normal))[:, None]*transmitted
    points[(nv >= 0) | (entry_t <= 0)] = np.nan
    return points


def normal_from_parameters(parameters):
    n = np.array([parameters[0], parameters[1], -1.0])
    return n / np.linalg.norm(n)


def observations(path, seed=42, count=600):
    """Read only; preserve full 2-D flow and require reciprocal source support."""
    with np.load(path) as p:
        f, b = p['forward'], p['backward']
        y, x = np.indices(f.shape[1:], dtype=np.float32)
        back = np.stack([cv2.remap(b[k], x+f[0], y+f[1], cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=float('nan'))
                         for k in range(2)])
        right_support = cv2.remap(p['right_roi'].astype(np.uint8), x+f[0], y+f[1],
                                  cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
        valid = p['left_roi'] & (right_support > 0) & (np.linalg.norm(f+back, axis=0) < 1.5)
        yy, xx = np.where(valid)
        available = len(xx)
        choose = np.random.default_rng(seed).choice(available, min(count, available), replace=False)
        xx, yy = xx[choose], yy[choose]
        uv0 = np.column_stack([xx, yy]).astype(float)
        uv1 = uv0 + f[:, yy, xx].T
        P0, P1 = p['P0'].copy(), p['P1'].copy()
    rays = []
    centers = []
    for uv, P in [(uv0, P0), (uv1, P1)]:
        inv = np.linalg.inv(P[:, :3])
        v = np.column_stack([uv, np.ones(len(uv))]) @ inv.T
        rays.append(v / np.linalg.norm(v, axis=1)[:, None])
        centers.append(-inv @ P[:, 3])
    return rays, centers, available


def residual(parameters, rays, centers, fixed_depth=None):
    n = normal_from_parameters(parameters)
    c = parameters[2]
    d = parameters[3] if fixed_depth is None else fixed_depth
    q0, q1 = [bottom_intersections(v, C, n, c, d) for v, C in zip(rays, centers)]
    # Angular-scale residual, in radians, compared at independently traced bottom.
    distance = .5*(np.linalg.norm(q0-centers[0], axis=1)+np.linalg.norm(q1-centers[1], axis=1))
    return np.nan_to_num((q0-q1)/distance[:, None], nan=1e3).ravel()


def fit(rays, centers, fixed_depth=None):
    outcomes = []
    for depth in [.01, .05, .15]:
        initial = [-1.2, -1.7, .30, depth]
        lower, upper = [-10, -10, .005, .0001], [10, 10, 3.0, 1.0]
        if fixed_depth is not None:
            initial, lower, upper = initial[:3], lower[:3], upper[:3]
        solution = least_squares(residual, initial, args=(rays, centers, fixed_depth),
                                 bounds=(lower, upper), max_nfev=300,
                                 x_scale='jac', ftol=1e-10, xtol=1e-10, gtol=1e-10)
        outcomes.append(solution)
    return min(outcomes, key=lambda s: np.linalg.norm(s.fun))


def describe(solution, test_rays, centers, fixed_depth=None):
    # Condition number explicitly depends on parameterization (ratios, meters).
    s = np.linalg.svd(solution.jac, compute_uv=False)
    return dict(normal=normal_from_parameters(solution.x).tolist(),
                offset_m=float(solution.x[2]),
                water_depth_m=float(solution.x[3] if fixed_depth is None else fixed_depth),
                train_ray_closure_rms_rad=float(np.sqrt(np.mean(solution.fun**2))*np.sqrt(3)),
                heldout_ray_closure_rms_rad=float(np.sqrt(np.mean(residual(solution.x, test_rays, centers, fixed_depth)**2))*np.sqrt(3)),
                jacobian_singular_values=s.tolist(), jacobian_condition=float(s[0]/s[-1]),
                active_bounds=solution.active_mask.tolist(), solver_success=bool(solution.success))


def main():
    records = []
    pooled = [[], []]
    hashes = {}
    for t in [1, 2, 3]:
        path = ROOT/'surface_chain_raft_centered'/f'frame_{t:02d}_correspondences.npz'
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        rays, centers, available = observations(path)
        for i in [0, 1]: pooled[i].append(rays[i])
        train, test = [v[::2] for v in rays], [v[1::2] for v in rays]
        solution = fit(train, centers)
        records.append(dict(time_s=t, available_correspondences=available,
                            train_count=len(train[0]), heldout_count=len(test[0]),
                            fit=describe(solution, test, centers)))
    rays = [np.concatenate(v) for v in pooled]
    train, test = [v[::2] for v in rays], [v[1::2] for v in rays]
    solution = fit(train, centers)
    profiles = []
    for depth in [solution.x[3]*.5, solution.x[3], solution.x[3]*2]:
        profiles.append(describe(fit(train, centers, depth), test, centers, depth))
    for path, value in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == value
    result = dict(status='REFRACTION_HYPOTHESIS_DIAGNOSTIC_NOT_HEIGHT_MEASUREMENT',
                  source_identity='USER_CONFIRMED_BOTTOM_TEXTURE_NO_SURFACE_MARKERS',
                  geometry_status='UNAPPROVED_CANDIDATE_UNCHANGED',
                  assumptions={'water_refractive_index':1.333, 'source':'IDEAL_ASSUMPTION_NOT_MEASURED',
                               'surface':'static plane', 'bottom':'parallel plane, USER_SPECIFIED_MODEL_ASSUMPTION',
                               'interfaces':'single air-water interface, unverified for all pixels'},
                  random_seed=42, frames=records, pooled=describe(solution, test, centers),
                  depth_profiles=profiles, source_sha256=hashes,
                  produces_water_height=False)
    out = ROOT/'refraction_probe'; out.mkdir(exist_ok=True)
    (out/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
