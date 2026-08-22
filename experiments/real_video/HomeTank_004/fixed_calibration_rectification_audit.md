# HomeTank_004 fixed-calibration rectification audit

## Scope and immutable status

This audit reviews only the OpenCV calibration-to-WASS fixed-extrinsic
convention. It does not modify the calibration result or adapter, rerun
calibration/WASS, change candidates, or inspect wave data. The immutable states
remain `CALIBRATION_QUALITY_FAIL`, `approved_for_wass=false`, and
`FAILED_AT_WASS_RECTIFICATION`.

## 1. OpenCV convention

OpenCV defines the `stereoCalibrate` output R/T as the change of basis from the
first camera coordinate system to the second:

`X_second = R * X_first + T`.

The project calls `stereoCalibrate(objects, left, right, K0, D0, K1, D1, ...)`,
so first=cam0/LEFT and second=cam1/RIGHT. The serialized convention
`X_cam1 = R_right_from_left * X_cam0 + T_right_from_left` is therefore correct.
Source: [OpenCV camera-calibration reference](https://docs.opencv.org/5.0/main_modules/calib.html).

## 2. WASS convention

WASS 1.11 loads ext_R/ext_T into `env.R/env.T`, assigns camera 0 pose to I/0,
and assigns camera 1 pose to R/T. Its projection matrices are consequently
`P0=K0[I|0]` and `P1=K1[R|T]`. WASS therefore expects the same transform:

`X_cam1 = ext_R * X_cam0 + ext_T`.

WASS also computes the inverse internally as `Rinv=R^T` and
`Tinv=-R^T*T`. When Tx is negative it performs its documented auto left/right
swap and swaps R/T with those inverse values before rectification. The static
trial log shows this exact branch. Sources: WASS commit `6b82aeb`,
[`load_data`, pose construction and scale normalization](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp#L326-L377), and
[`swapLeftRight`/rectification](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp#L256-L286).

## 3. Adapter behavior and conversion decision

The adapter validates R[3,3] and T[3,1], then writes them directly as ext_R and
ext_T. It does not transpose, invert, change sign, or rescale the serialized T.
Its sidecar records `X_cam1 = R_01 @ X_cam0 + T_01_m`.

This direct mapping is correct. Pre-converting to
`R'=R^T`, `T'=-R^T*T` is **not required** and would reverse an already-correct
cam0-to-cam1 transform. WASS performs that inversion itself only when its
internal left/right swap requires it.

## 4. Left/right trace

| Boundary | cam0 | cam1 | Result |
|---|---|---|---|
| manifest | LEFT / iQOO Neo5S | RIGHT / iQOO Z10 Turbo+ | consistent |
| calibration points | first / `left_image_points` | second / `right_image_points` | consistent |
| calibration corner QA | left grid | right grid, original order for all 192 pairs | consistent |
| WASS prepare input | `--c0` | `--c1` | consistent |
| WASS initial load | image 0 / left | image 1 / right | consistent |

`auto-swapping left-right images` in WASS is not evidence that the manifest is
reversed. It is WASS's internal response to negative Tx under its disparity
orientation convention, accompanied by the mathematically correct inverse R/T.
No upstream left/right swap was found.

## 5. Translation and units

The unchanged OpenCV translation is:

`T = [-0.0588588027, 0.0125879387, -0.0330873805] m`

and `||T|| = 0.0686847116 m`. Calibration object points used the configured
0.020 m checker square, so T has metre units. Its norm differs from the manual
0.070 m baseline by 1.879%, independently supporting the unit order of
magnitude. There is no mm/m mismatch in the adapter.

WASS normalizes T to its internal camera distance (1.0) before projection and
rectification. Multiplying T by 1000 would therefore not change its normalized
direction or the rectification geometry. Unit scale is not the cause of the
reported empty ROI.

## 6. Failure interpretation and recommendation

The convention audit finds:

- `R/T_DIRECTION_CONVERSION_REQUIRED = false`;
- `LEFT_RIGHT_INPUT_ERROR = false`;
- `TRANSLATION_UNIT_ERROR = false`.

The failure remains consistent with the numerical calibration geometry and
WASS rectification policy, not an adapter convention error. In particular,
WASS calls OpenCV rectification with already-undistorted images, zero distortion
and alpha=1.0, then rejects a zero valid ROI as `the epipole lies inside the
image plane`. The earlier calibration diagnostic used its own rectification
settings and already exhibited large vertical inconsistency.

Recommended next step: perform a read-only numerical rectification-policy audit
of the unchanged Candidate A geometry (ROI, epipole location, alpha and WASS
auto-swap branch). Do not invert R/T in the adapter, do not alter the calibration
result, and do not run wave data.
