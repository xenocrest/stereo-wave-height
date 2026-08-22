# HomeTank_004 Result Summary

Status: `STRICT_CALIBRATION_FAILED`

Capture: `INPUT_DATA_READY`

Calibration: `CALIBRATION_QUALITY_FAIL`

WASS: `STATIC_TRIAL_FAILED_AT_RECTIFICATION`

Height reconstruction: `NOT_RUN`

The official OpenCV calibration attempt returned finite matrices but failed
the frozen reprojection, epipolar and rectification quality gates. It is not
approved for WASS. Corrected manual geometry gives a 0.070 m baseline versus
0.068685 m calibrated, so physical baseline plausibility passes independently;
the strict failure remains unchanged. Calibrated K/D/R/T are the primary reconstruction
parameters. Manual geometry is retained only as an independent physical sanity
check and must not replace calibrated T. The planned static-only comparison is
`FULL_CALIBRATION` vs `CALIBRATION_ZERO_DISTORTION` vs
`SPECIFICATION_INTRINSIC_REFERENCE`.

Candidate A `FULL_CALIBRATION` static execution completed with
`STATIC_GEOMETRY_INVALID`. Prepare and sparse match passed for three PTS-paired
frames, but the first stereo call failed during fixed-geometry rectification
because the epipole lay inside the image plane. No XYZ was produced; B/C,
autocalibrate, and wave were not run. This does not change
`CALIBRATION_QUALITY_FAIL` or `approved_for_wass=false`.

Next: `REVIEW_FIXED_CALIBRATION_RECTIFICATION_FAILURE`.
