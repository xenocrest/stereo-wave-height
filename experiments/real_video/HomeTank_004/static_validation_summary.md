# HomeTank_004 Static Validation Summary

## Frozen input and configuration

This summary uses the existing three-frame `FULL_CALIBRATION` static trial. The
OpenCV `K0/D0/K1/D1/R/T` values are unchanged. WASS rectification remains
`alpha=0.0` with zero disparity, and plane extraction remains 400 rounds,
distance threshold `1.0`, and `VALID_POINT_SAMPLING`. No WASS stage was rerun
for this summary and no wave data was processed.

Historical status remains `CALIBRATION_QUALITY_FAIL` and
`approved_for_wass=false`.

## Per-frame reconstruction

`valid point count` is the triangulated valid population before largest
component retention. `XYZ point count` and water-plane inliers are the retained
`mesh_cam.xyzC` population. The inlier ratio is relative to that retained
component.

| Frame | cam0/cam1 timestamp (s) | XYZ points | Valid points | Plane inliers | Inlier ratio | Mean Z (m) |
|---|---|---:|---:|---:|---:|---:|
| 000000 | 10.012256 / 10.100267 | 167,581 | 216,874 | 167,581 | 1.0000 | 0.2907236481 |
| 000001 | 27.006311 / 27.100722 | 33,286 | 133,968 | 33,286 | 1.0000 | 0.3311206990 |
| 000002 | 44.000511 / 44.101167 | 34,411 | 141,950 | 34,411 | 1.0000 | 0.2338873373 |

## Water-plane fits

All equations use metres and the camera-coordinate model `z = a*x + b*y + c`.

| Frame | a | b | c (m) | RMS (mm) | Mean signed residual (mm) | Max absolute residual (mm) |
|---|---:|---:|---:|---:|---:|---:|
| 000000 | 0.4604331984 | 0.0784329395 | 0.3971745173 | 2.2491 | -0.0137 | 74.2757 |
| 000001 | 0.3409947789 | 0.0361078488 | 0.3878047532 | 2.1611 | -0.0126 | 33.0415 |
| 000002 | 0.5856541884 | -0.0393184049 | 0.4008669322 | 2.0065 | -0.0100 | 11.9686 |

## Static stability

The maximum pairwise plane-normal difference is `12.1664 deg`. Plane offset
`c` spans `0.0130622 m`, decoded point-cloud mean Z spans `0.0972334 m`, and
plane RMS spans `0.0002426 m`. Although each retained cloud contains a plane
with a similar millimetre-scale RMS, the plane orientation and reconstructed
depth are not stable across the three timestamps.

The frozen classification is therefore:

`STATIC_VALIDATION_FAIL / STATIC_BASELINE_UNSTABLE`.

## Physical scale check

The unchanged calibrated baseline is `0.0686847116 m`; the corrected
user-specified measurement is `0.070 m`, a relative difference of `1.879%`.
This is a sanity comparison only. HomeTank_004 has no registered independent
numeric tank dimension or ruler interval against which a reconstructed object
length can be checked, so `scale_validation=FAIL`. No scale correction was
applied.

## Wave-stage use

This result is frozen as evidence that the static pipeline can generate XYZ and
detect planes, but it is **not** an approved height-reference baseline. Wave
processing remains unauthorized until the static inter-frame instability is
resolved without changing historical calibration status by assertion.
