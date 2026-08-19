# Calibration preflight and dataset gates

## Purpose

This infrastructure prevents static/wave recording before the calibration
target and dataset are known to be usable. It is camera-vendor independent and
does not run WASS.

The frozen HomeTank_003 target is a standard alternating checkerboard with
9 x 6 internal corners, 10 x 7 physical squares, and 0.020 m square spacing.
The machine-readable definition and review thresholds are in
[checkerboard_9x6_20mm.yaml](../../configs/calibration/checkerboard_9x6_20mm.yaml).

## Gate A — target detectability

Each canonical grayscale image is processed by OpenCV
`findChessboardCornersSB` with normalization, exhaustive search, and accuracy
flags, followed by explicit `cornerSubPix`. A pass requires all 54 points in
both cameras, configured sharpness/coverage/edge/perspective checks, and one
timestamp- and geometry-consistent stereo pair.

The frame assessment reports corner count, convex-hull coverage, bounding-box
fraction, Laplacian-variance sharpness, nearest image-edge margin, saturation,
perspective score, warnings, and an explicit rejection reason. Current numeric
thresholds are configurable project heuristics for capture feedback, not
universal scientific standards.

## Image-only pose signature

No preliminary K is assumed. Each complete board produces:

```text
[center_x/image_width,
 center_y/image_height,
 log(convex_hull_area/image_area),
 row_angle/pi,
 column_angle/pi,
 cosine(row_direction,column_direction),
 opposite-edge perspective difference]
```

This signature represents location, scale, in-plane direction, skew, and
projective foreshortening. Weighted Euclidean distance is used only as an
explainable near-duplicate test; it is not a physical camera pose estimate.

## Candidate extraction and stereo pairing

A PTS-aware decoder supplies canonical frames with explicit timestamps. The
generic extractor samples those timestamps at a configured 0.25--0.5 s-like
interval, assesses them, then uses deterministic greedy farthest-point
selection. Repeated frames from a 1--2 s hold form one near-duplicate group;
the sharpest member is preferred. The interface rejects `UNKNOWN/TODO`
timestamp provenance and never assumes equal left/right frame indices.

Left/right candidates are paired one-to-one using timestamp proximity and pose
signature distance. Every accepted pair records both timestamps, delta time,
and geometry distance.

## Gate B — dataset diversity

The minimum attempt threshold is 12 independent stereo poses. Counts 12--19,
or incomplete position/scale/orientation coverage, produce
`CALIBRATION_DATASET_READY_WITH_WARNING`. At least 20 independent poses with
adequate continuous coverage produces `CALIBRATION_DATASET_READY`; the capture
target is 20--30. Below 12 is `CALIBRATION_DATASET_INSUFFICIENT`.

Position coverage uses normalized centre spans, scale diversity uses log-area
span, and orientation diversity uses row/column angle spans. These are
continuous diagnostics rather than semantic ML labels.

## Calibration-result quality gate

After calibration, a serializable summary records initial/accepted/rejected
views, one documented outlier-filtering pass, mono and stereo RMS, per-view
rejections, R/T-derived baseline, epipolar RMS, rectification RMS, and valid
rectification status. Classifications include:

- `CALIBRATION_PASS`
- `CALIBRATION_DATASET_INSUFFICIENT`
- `CALIBRATION_HIGH_REPROJECTION_ERROR`
- `CALIBRATION_POOR_EPIPOLAR_GEOMETRY`
- `CALIBRATION_RECTIFICATION_FAIL`
- `CALIBRATION_RESULT_INCOMPLETE`

The quality classifier reports supplied evidence and never iteratively deletes
views. Thresholds remain configurable and must be tied to an experiment review.

## GUI boundary

The Calibration page displays the shared assessment, diversity, and quality
models. It does not recalculate computer-vision metrics. Before HomeTank_003 is
captured it intentionally shows `PENDING / NOT_CAPTURED`; synthetic fixtures
are test evidence only and never become experiment results.
