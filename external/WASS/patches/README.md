# WASS adapter-interface patches

This directory records small, reviewable interface patches required by the
project. It does not vendor or modify the WASS source tree. Patches are applied
only to an isolated external build; the production runtime and upstream
repository remain unchanged.

`fixed_calibration_rectification_policy.patch` adds two optional `incfg` keys:

- `RECTIFICATION_ALPHA`, default `1.0`;
- `RECTIFICATION_ZERO_DISPARITY`, default `false`.

The defaults preserve WASS 1.11 behavior (`cv::stereoRectify` flags `0`, alpha
`1.0`). The patch changes only rectification call policy and logging. It does
not change `K`, `D`, `R`, `T`, matching, triangulation, filtering, or plane
estimation.

`plane_ransac_valid_point_sampling.patch` adds an optional
`PLANE_RANSAC_SAMPLING_MODE`. Its default preserves full-image random sampling;
the opt-in `VALID_POINT_SAMPLING` population contains only already-valid XYZ
points. RANSAC rounds, distance threshold, plane model and per-point inlier
comparison remain unchanged.
