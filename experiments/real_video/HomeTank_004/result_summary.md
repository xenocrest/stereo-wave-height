# HomeTank_004 Result Summary

Status: `STRICT_CALIBRATION_FAILED`

Capture: `INPUT_DATA_READY`

Calibration: `CALIBRATION_QUALITY_FAIL`

WASS: `NOT_RUN`

Height reconstruction: `NOT_RUN`

The official OpenCV calibration attempt returned finite matrices but failed
the frozen reprojection, epipolar and rectification quality gates. It is not
approved for WASS. Corrected manual geometry gives a 0.070 m baseline versus
0.068685 m calibrated, so physical baseline plausibility passes independently;
the strict failure remains unchanged. Calibrated K/D/R/T are the primary reconstruction
parameters. Manual geometry is retained only as an independent physical sanity
check and must not replace calibrated T. The planned static-only comparison is
`FULL_CALIBRATION` vs `CALIBRATION_ZERO_DISTORTION` vs
`SPECIFICATION_INTRINSIC_REFERENCE`. Next:
`STATIC_TRIAL_WITH_CALIBRATION_PARAMETERS`.
