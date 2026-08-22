# HomeTank_004 rectification-policy compatibility test

## Purpose and frozen candidate

This test asks whether Candidate A `FULL_CALIBRATION` can pass WASS fixed
stereo under A0-A3 rectification policies. K0/D0/K1/D1/R/T, camera roles,
baseline, videos, timestamps, and synchronization were unchanged. Candidate
B/C, autocalibration, and wave data were not run.

## Production-interface boundary

WASS `1.11_heads/master-0-g6b82aeb` does not expose OpenCV rectification alpha
or flags through its configuration or command line. The production source
hard-codes `flags=0` and `alpha=1.0` in `cv::stereoRectify`; its only related
configuration selects a separate custom rectifier and its ROI behavior. See
[`wass_stereo.cpp`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp#L483-L566).

The existing isolated diagnostic build is already classified by this project
as not numerically equivalent to production and cannot provide formal WASS
results. Patching WASS, intercepting OpenCV, or pre-rectifying images with
derived K/R/T would violate the frozen-Candidate-A requirement.

A minimal policy-capability adapter was therefore added. It models A0-A3 and
fails explicitly when the production runtime cannot represent a policy. It
does not modify calibration values, images, WASS, or reconstruction code.

## Test matrix

OpenCV 5.0.0 independently evaluated the exact post-prepare/post-auto-swap WASS
geometry: undistorted images, zero D, K1/K0 and `R^T,-R^T*T`. Epipoles remain
outside the image at left `(4277.6657,134.7423)` px and right
`(3786.6227,28.8087)` px.

| Test | alpha | flags | OpenCV result | left ROI | right ROI | WASS stereo |
|---|---:|---|---|---|---|---|
| A0 | 0.0 | `CALIB_ZERO_DISPARITY` | PASS | `[0,0,1920,1080]` | `[0,0,1920,1079]` | `NOT_RUN_UNSUPPORTED_BY_PRODUCTION_RUNTIME_INTERFACE` |
| A1 | 0.5 | `CALIB_ZERO_DISPARITY` | PASS | `[0,200,1232,505]` | `[0,58,1037,548]` | `NOT_RUN_UNSUPPORTED_BY_PRODUCTION_RUNTIME_INTERFACE` |
| A2 | 1.0 | `CALIB_ZERO_DISPARITY` | PASS, zero ROI | `[0,0,0,0]` | `[0,0,0,0]` | `NOT_RUN_UNSUPPORTED_BY_PRODUCTION_RUNTIME_INTERFACE` |
| A3 | 0.0 | default/0 | PASS | `[0,0,1920,1080]` | `[0,0,1920,1079]` | `NOT_RUN_UNSUPPORTED_BY_PRODUCTION_RUNTIME_INTERFACE` |

The production compiled policy is alpha=1.0, flags=0. It is outside A0-A3 and
has already failed with zero ROI and return code -1073740791 in the frozen
static trial. It was not rerun.

## Compatibility decision

No test can satisfy both required conditions—nonzero ROI and WASS stereo PASS—
through the production interface. Therefore:

`rectification_policy_compatible=false`

`classification=BLOCKED_BY_PRODUCTION_WASS_POLICY_INTERFACE`

There is no successful policy, no static reconstruction, and no XYZ/plane
result. An offline OpenCV ROI pass is not reported as WASS compatibility or a
calibration pass. `CALIBRATION_QUALITY_FAIL` and `approved_for_wass=false`
remain unchanged.

## Recommended next step

Obtain an official policy-capable WASS runtime or first establish a numerically
equivalent isolated build against the production static baseline. Only then may
one predeclare and run A0 first, stopping at the first WASS stereo PASS. Do not
test Candidate B/C or wave data to bypass this interface limitation.
