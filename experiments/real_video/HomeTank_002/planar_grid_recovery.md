# HomeTank_002 planar-grid recovery attempt

## Outcome

The custom target is recoverable as a projective 9 x 6 line lattice, but the
existing videos do **not** pass the calibration quality gate. The experiment
therefore remains `CALIBRATION_DATA_INSUFFICIENT`; no recovered calibration is
authorized for WASS.

The earlier standard-checkerboard result is retained: it was a detector-model
failure (`0/88` and `0/89`), not proof that the line intersections were absent.
The new semi-automatic detector recovered complete, ordered 54-point lattices
in multiple frames from both cameras, establishing `GRID_RECOVERY_FEASIBLE`.

## Method and point identity

An operator supplies the four outer target corners in physical order: object
origin, +X end, opposite corner, and +Y end. The image is projectively
rectified, vertical and horizontal line-gradient profiles are searched near
the expected lattice positions, all 54 intersections are mapped back, and
`cornerSubPix` refines them. Points outside the image, weak line families, and
subpixel escapes are explicit failures. No missing point is fabricated.

The physical mapping remains
`(X,Y,Z)=(column*0.020,row*0.020,0) m`, row-major. This explicit orientation is
required because the symmetric grid cannot identify its physical origin by
appearance alone.

## Representative-frame gate

Seven frames per camera were assessed at 5, 15, 35, 45, 55, 65, and 75 s.

| Camera | Complete 54-point timestamps (s) | Rejected timestamps (s) |
|---|---|---|
| cam0 / left / Neo5S | 5, 15, 45, 55, 75 | 35, 65 |
| cam1 / right / Z10 Turbo+ | 5, 35, 45, 75 | 15, 55, 65 |

Rejections correspond to clipping or insufficient line-gradient support under
the supplied quadrilateral. Diagnostic overlays and per-frame measurements are
stored outside Git under
`D:\research\stereo-wave-height-data\HomeTank_002\grid_recovery_diagnostics`.

## Calibration quality gate

After Gate 1 passed, 12 time-neighbour candidates from several held poses were
tested. Nine pairs had complete 54-point recovery, but they represented only
three independent pose groups. The diagnostic OpenCV calibration produced:

| Metric | Result |
|---|---:|
| cam0 mono RMS | 3.6508 px |
| cam1 mono RMS | 5.8782 px |
| stereo RMS | 7.6597 px |
| symmetric epipolar RMS | 16.9093 px |
| diagnostic baseline magnitude | 0.11934 m |

These values fail quality control. The right-camera distortion solution is
also unstable and the rectification valid ROIs are empty. In addition, several
video poses visibly bend the paper/board, violating the single rigid plane
assumed by `(X,Y,0)`. The numerical K/D/R/T solution is therefore rejected and
is not published as usable calibration.

## Decision

- `standard_checkerboard_detection: FAIL`
- `custom_planar_grid_recovery: PASS`
- `custom_planar_grid_calibration: FAIL`
- final experiment status: `CALIBRATION_DATA_INSUFFICIENT`
- WASS/static/wave/H: not run

The raw HomeTank_002 videos are retained. No re-record was requested before the
custom recovery attempt. After this completed attempt, a new calibration
capture is recommended: use a verified rigid, flat target and collect at least
12--20 complete, synchronized, genuinely diverse stereo poses. HomeTank_002
must not be deleted or its failure history overwritten.
