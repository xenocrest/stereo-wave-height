# HomeTank_002 calibrated-retry result

## Final classification

`CALIBRATION_DATA_INSUFFICIENT`

- `standard_checkerboard_detection: FAIL`
- `custom_planar_grid_recovery: PASS`
- `custom_planar_grid_calibration: FAIL`

HomeTank_002 raw videos are retained. No re-record was requested before the
custom grid recovery attempt.

HomeTank_002 is the calibrated retry following HomeTank_001's `CALIBRATION_REQUIRED` uncalibrated trial. It uses a newly defined physical assignment: cam0/left is iQOO Neo5S and cam1/right is iQOO Z10 Turbo+. No device-side binding was inherited from HomeTank_001.

## Video and orientation checks

All six expected MP4 files exist and are readable. They are 1920 x 1080, nominal 60 fps, with H.264 for Neo5S and HEVC for Z10 Turbo+. Neo5S streams contain a -180-degree display transform in this experiment, while Z10 streams contain no display rotation. Canonical calibration frames therefore applied 180 degrees to cam0 and identity to cam1. Representative visual inspection confirmed both views were upright after those transforms.

Detailed durations, rates, frame counts, and timing assessments are recorded in [video_metadata_summary.yaml](video_metadata_summary.yaml).

## Declared calibration target

- inner corners: `(9, 6)` = 54 points;
- square size: `20.0 mm = 0.020 m`;
- object points: `(column * 0.020, row * 0.020, 0)` metres.

The physical target consists of white cells separated by dark grid lines. It
does not have the polarity required by a standard checkerboard detector. A
subsequent semi-automatic projective line-grid recovery was therefore attempted
without changing the declared 9 x 6 internal-intersection topology.

## Detection evidence and gate

OpenCV 5.0.0 `findChessboardCornersSB` with normalization, exhaustive search, and accuracy flags was run on uniformly sampled canonical frames across both complete calibration videos:

| Stream | Frames tested | Complete 9 x 6 detections |
|---|---:|---:|
| cam0 / left / Neo5S | 88 | 0 |
| cam1 / right / Z10 Turbo+ | 89 | 0 |
| shared stereo pairs | - | 0 |

That standard-detector result remains historical evidence, but it is no longer
interpreted as absence of grid points. The custom detector recovered multiple
complete, subpixel-refined 54-point frames in each camera, so the recovery gate
is `GRID_RECOVERY_FEASIBLE`.

A controlled calibration attempt found nine complete stereo pairs but only
three independent pose groups. Its diagnostic solution failed quality checks:
mono RMS was 3.6508/5.8782 px, stereo RMS 7.6597 px, and symmetric epipolar RMS
16.9093 px. Some poses also visibly bend the target, invalidating the assumed
rigid plane. The resulting K/D/R/T and 0.11934 m diagnostic baseline are
explicitly rejected and must not be used. Full evidence is in
[planar_grid_recovery.md](planar_grid_recovery.md).

## Downstream status

- static synchronization: not run;
- static WASS: not run;
- xyzC: not produced;
- wave subset: not run;
- qualitative H: not computed.

This result does not evaluate WASS or water-surface observability. WASS, static,
wave, and H processing were not run.

## Recommended recapture after rescue attempt

The existing custom grid has now been tested rather than discarded. A new
capture is nevertheless recommended because the available complete stereo
poses are insufficiently diverse and the target is not reliably planar. Use a
rigid, flat, metrically verified target and capture at least 12--20 complete
shared views spanning centre, edges, distance, tilt, and in-plane rotation
while keeping the stereo rig fixed.
