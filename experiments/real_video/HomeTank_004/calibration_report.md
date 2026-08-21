# HomeTank_004 final OpenCV calibration attempt

## Conclusion

`STRICT_CALIBRATION_FAILED = true`

`CALIBRATION_QUALITY_FAIL`

`approved_for_wass = false`

`NEXT = COARSE_GEOMETRY_VALIDATION`

This final strict mobile calibration attempt used only the frozen OpenCV
official backend. It did not run WASS or introduce a detector, grid recovery,
optimizer, flag search, or repeated outlier deletion.

## Detection and pairing

Both calibration videos were decoded in canonical orientation at approximately
5 Hz using decoder PTS. Cam0 applied exactly one 180-degree rotation; cam1 used
identity. The frozen native -> 0.5x -> CLAHE strategy found 233/588 complete
cam0 grids (39.63%) and 328/587 cam1 grids (55.88%). Almost all detections
required the single 0.5x fallback; CLAHE added none.

The input-inspection synchronization candidate was 0 s. Unique nearest-PTS
pairing within 0.12 s produced 192 stereo candidates. Residual median was
-8.928 ms and P95 absolute residual was 14.398 ms. This timing is sufficient
for this calibration attempt only and does not finalize static/wave sync.

Each pair compared the normalized right grid in original and fully reversed
54-point order against the left grid. All 192 selected the original order; the
smallest alternative/selected RMS ratio was 16.42, so no pair was ambiguous.
This QA changed no OpenCV corner coordinates.

The existing deterministic pose-diversity selector reduced 192 temporally dense
pairs to 12 independent poses. The dataset was therefore
`DATASET_USABLE_WITH_WARNING`, exactly at the minimum allowed count.

## Official calibration result

The 12 pairs were passed unchanged to `calibrateCamera(flags=0)`, followed by
`stereoCalibrate(CALIB_FIX_INTRINSIC)` and
`stereoRectify(CALIB_ZERO_DISPARITY, alpha=0)`.

| Metric | Result |
|---|---:|
| cam0 mono RMS | 4.380506 px |
| cam1 mono RMS | 4.525325 px |
| stereo RMS | 7.922425 px |
| symmetric epipolar RMS | 9.508413 px |
| rectified vertical RMS | 21.122547 px |
| rectified vertical median | 10.994904 px |
| rectified vertical P95 | 46.281027 px |
| common ROI | `[0, 0, 1920, 1079]` |
| common ROI fraction | 0.999074 |
| recovered baseline | 0.068685 m |
| relative rotation angle | 14.652724 deg |

The predeclared one-shot rule could reject a pair only if its mono per-view RMS
exceeded median + 3 MAD and at least 12 views remained. Because the initial set
already contained exactly 12 views, zero views were rejected. No iterative
deletion was attempted.

The solver returned finite matrices, but all major accuracy metrics fail the
existing quality thresholds. The rectification preview also shows large
vertical inconsistency. The exact physical cause is not isolated by this
attempt; limited independent-pose count and target/image imperfections remain
data risks, not backend implementation errors.

## Physical sanity and fallback

The recovered baseline is 0.068685 m. The actual baseline remains `UNKNOWN` in
`measured_geometry.yaml`, so the scale sanity check cannot be completed. The
14.65-degree relative rotation is likewise not independently measured. These
outputs are diagnostic and must not be exported to WASS.

The coarse fallback still needs:

- `baseline_m`;
- `cam0_height_to_water_m` and `cam1_height_to_water_m`;
- `cam0_pitch_deg` and `cam1_pitch_deg`;
- yaw/roll/height differences if available;
- approximate `focal_px` or HFOV;
- explicit assumed principal point and distortion model.

No further checkerboard capture or detector development is proposed. The next
stage is the already-defined non-metrological coarse-geometry closure route.
