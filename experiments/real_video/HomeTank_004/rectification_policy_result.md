# HomeTank_004 fixed-calibration rectification policy result

## Scope and invariants

This controlled test adds a rectification-policy configuration interface to
WASS fixed calibration. Candidate A remained `FULL_CALIBRATION`: the OpenCV
`K0/D0/K1/D1/R/T`, camera roles, videos, timestamps, and synchronization were
unchanged. `wass_autocalibrate` and wave reconstruction were not run.

The policy changes only the two arguments passed to `cv::stereoRectify`. It
does not change calibration or dense-reconstruction mathematics. Historical
status remains `CALIBRATION_QUALITY_FAIL` and `approved_for_wass=false`.

## Interface and backward compatibility

The project `RectificationPolicy` defaults to `alpha=1.0` and
`zero_disparity=false`, which derives OpenCV `flags=0` and preserves the
observed WASS 1.11 behavior. HomeTank_004 explicitly selected:

```yaml
rectification:
  alpha: 0.0
  zero_disparity: true
```

The policy-capable runtime therefore received `RECTIFICATION_ALPHA=0` and
`RECTIFICATION_ZERO_DISPARITY=true`, mapping to
`cv::CALIB_ZERO_DISPARITY` (`1024`).

## Runtime qualification

The isolated executable uses upstream commit `6b82aeb...` and dynamically
links the frozen modular OpenCV 4.6 DLL set used by the production runtime. It
was compiled with MSVC 19.44 rather than the unrecovered production compiler.
Consequently numerical equivalence to the production executable is
`NOT_ESTABLISHED`; this run is a controlled compatibility test, not a
replacement production WASS result.

## Static run

The existing three timestamp-paired static workspaces were copied outside Git.
Their completed production `prepare` and `match` results were reused;
Candidate-A external calibration was unchanged and autocalibration remained
disabled.

| Stage | Result | Evidence |
|---|---|---|
| prepare | `PASS_REUSED` | three prior paired workdirs |
| match | `PASS_REUSED` | three prior sparse-match results |
| rectification, frame 000000 | `PASS` | log reports `alpha=0, flags=1024` and map generated |
| dense stereo | `PASS` | completed successfully |
| triangulation | `PASS` | 216,874 valid points |
| largest component | `PASS` | 167,581 points |
| plane RANSAC | `FAIL` | 400 rounds, 0 best inliers, return code -1 |
| overall WASS stereo | `FAIL` | stopped at first failed frame |

The original `RECTIFICATION_POLICY_ROI_INCOMPATIBILITY` is therefore resolved
for A0, but Candidate A does not complete the WASS stereo pipeline. No
`mesh_cam.xyzC` was generated, so XYZ range, static plane RMS, and tilt are
`NOT_AVAILABLE`. Later static frames were not run after the first formal
failure, and wave was not run.

## Conclusion

`rectification_policy_test_status` is
`ROI_INCOMPATIBILITY_RESOLVED_STEREO_PIPELINE_NOT_PASSED`. Policy compatibility
must not be interpreted as calibration approval. The next controlled task
should diagnose the fixed Candidate-A plane-RANSAC failure using this same
static frame and frozen policy; it should not test wave or silently alter
calibration/reconstruction thresholds.
