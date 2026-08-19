# HomeTank_002 calibrated-retry result

## Final classification

`CALIBRATION_DATA_INSUFFICIENT`

HomeTank_002 is the calibrated retry following HomeTank_001's `CALIBRATION_REQUIRED` uncalibrated trial. It uses a newly defined physical assignment: cam0/left is iQOO Neo5S and cam1/right is iQOO Z10 Turbo+. No device-side binding was inherited from HomeTank_001.

## Video and orientation checks

All six expected MP4 files exist and are readable. They are 1920 x 1080, nominal 60 fps, with H.264 for Neo5S and HEVC for Z10 Turbo+. Neo5S streams contain a -180-degree display transform in this experiment, while Z10 streams contain no display rotation. Canonical calibration frames therefore applied 180 degrees to cam0 and identity to cam1. Representative visual inspection confirmed both views were upright after those transforms.

Detailed durations, rates, frame counts, and timing assessments are recorded in [video_metadata_summary.yaml](video_metadata_summary.yaml).

## Declared calibration target

- inner corners: `(9, 6)` = 54 points;
- square size: `20.0 mm = 0.020 m`;
- object points: `(column * 0.020, row * 0.020, 0)` metres.

The physical target visible in reviewed frames consists of white cells separated by dark grid lines. It does not show the alternating black/white regions required by a standard checkerboard detector. This is not treated as a 10 x 7 inner-corner board, and no custom line-grid calibration solver was introduced.

## Detection evidence and gate

OpenCV 5.0.0 `findChessboardCornersSB` with normalization, exhaustive search, and accuracy flags was run on uniformly sampled canonical frames across both complete calibration videos:

| Stream | Frames tested | Complete 9 x 6 detections |
|---|---:|---:|
| cam0 / left / Neo5S | 88 | 0 |
| cam1 / right / Z10 Turbo+ | 89 | 0 |
| shared stereo pairs | - | 0 |

With no complete detection, subpixel refinement, pose-diversity selection, mono calibration, outlier evaluation, and stereo calibration cannot be performed. All K, D, R, T, E, F, RMS, epipolar, rectification, and baseline result fields remain null rather than guessed.

The project rule requires at least approximately 10 diverse shared views to attempt calibration. The result therefore fails at the calibration gate as `CALIBRATION_DATA_INSUFFICIENT`.

## Downstream status

- static synchronization: not run;
- static WASS: not run;
- xyzC: not produced;
- wave subset: not run;
- qualitative H: not computed.

This result does not evaluate WASS or water-surface observability. The current blocker is solely the unusable calibration-target observation.

## Required recapture

Use a rigid and flat, high-contrast alternating black/white board. For the frozen `(9,6)` inner-corner definition it must contain 10 x 7 physical squares, each independently verified as 20.0 mm. Before recording the complete sequence, test one frame from both cameras and require successful 54-corner detection. Then capture 20–30 shared views spanning centre, edges, distance, tilt, and in-plane rotation while keeping the stereo rig fixed.
