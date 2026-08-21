# HomeTank_004 pre-capture software preparation

Status: `READY_FOR_FINAL_CAPTURE`

HomeTank_004 has not been captured. This document defines the software gate and
does not contain experimental results.

## MATURE_CODE_FIRST

For standard computer-vision operations, prefer established upstream
implementations. Project-owned code focuses on integration, experiment
management, WASS interoperability, wave-height computation, QA, and application
logic. The primary stereo-calibration implementation is the official OpenCV
pipeline. Custom calibration code is `LEGACY/EXPERIMENTAL` unless explicitly
re-enabled for a separately reviewed diagnostic task.

## Implementation ownership audit

| Area | Classification | HomeTank_004 role |
|---|---|---|
| video/frame input, ffprobe metadata, canonical orientation | KEEP | input infrastructure |
| result serialization, quality report, GUI model, WASS interface | KEEP | integration and gate |
| checkerboard detection | OFFICIAL_BACKEND | OpenCV `findChessboardCornersSB` |
| mono calibration | OFFICIAL_BACKEND | OpenCV `calibrateCamera` |
| stereo calibration | OFFICIAL_BACKEND | OpenCV `stereoCalibrate` |
| rectification and epipolar geometry | OFFICIAL_BACKEND | OpenCV `stereoRectify`, `computeCorrespondEpilines` |
| `planar_grid.py`, custom grid recovery, historical fallback tricks | EXPERIMENTAL/LEGACY | not on HomeTank_004 main path |

The wrapper is intentionally thin. It does not contain a custom detector,
optimizer, bundle adjustment, distortion model, stereo matcher, or point-cloud
solver.

## Frozen primary path

Target: 9 columns by 6 rows of **inner corners** (54 corners), corresponding to
10 by 7 physical squares. Configured square size is 0.020 m with provenance
`USER_SPECIFIED/CONFIGURED`; it is not independently measured by software.

Detection is limited to:

1. SB at canonical native resolution;
2. one SB attempt at 0.5 scale, mapped back to canonical pixels;
3. optional single native CLAHE+SB attempt only when explicitly enabled;
4. OpenCV `cornerSubPix` on the canonical native image.

No size sweep or threshold search is allowed. Monocular calibration calls
`calibrateCamera` with the standard five-coefficient model and flags `0`.
Stereo calibration uses the two monocular solutions with only
`CALIB_FIX_INTRINSIC`; it returns R, T, E and F. Rectification uses
`CALIB_ZERO_DISPARITY`, `alpha=0`, and reports both valid ROIs, their
intersection, and vertical disparity statistics. These choices use OpenCV's
public APIs and keep parameter meanings explicit; they do not mechanically copy
the older sample's joint-intrinsic flag set.

Sources: [OpenCV 4.x stereo calibration sample](https://github.com/opencv/opencv/blob/4.x/samples/cpp/stereo_calib.cpp) and [OpenCV calib3d API](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html).

## Golden-path gate

The external fixture is the official OpenCV 4.x `samples/data/leftNN.jpg` and
`rightNN.jpg` set. It was downloaded to an unversioned cache; no third-party
images are committed. Thirteen available pairs produced thirteen complete 9x6
stereo detections. The complete chain detection -> mono calibration -> fixed-
intrinsic stereo calibration -> epipolar diagnostics -> rectification passed.

The runtime available to this project reports OpenCV 5.0.0. Its Python public
API is compatible with the referenced 4.x calls; the upstream 4.x sample and
documentation remain the design reference. Recorded results are in
`opencv_golden_path_metrics.json`: mono RMS 0.1954/0.2070 px, stereo RMS 0.2168
px, epipolar RMS 0.1769 px, rectified vertical RMS 0.1707 px, and a non-empty
640x479 common ROI. The fixture uses 0.020 m only as a software-test scale
assumption, so its 0.06656 m recovered baseline is not a physical claim about
the OpenCV sample rig.

## High-risk convention audit

| # | Risk | Result | Evidence/control |
|---:|---|---|---|
| 1 | pattern size is squares rather than inner corners | PASS | `CheckerboardSpec(9,6)` gives 54 points |
| 2 | object-point order | PASS | row-major `(column*s,row*s,0)` test |
| 3 | square size changes ordering | PASS | scale enters coordinates only |
| 4 | left/right role drift | PASS | explicit cam0/left and cam1/right schema |
| 5 | R/T convention ambiguity | PASS | `X_right = R @ X_left + T`, inversion test |
| 6 | canonical rotation coordinate mismatch | PASS | canonical-only detection and 180-degree round-trip test |
| 7 | width/height transpose | PASS | explicit `image_size_wh`; official 640x480 fixture passes |
| 8 | unequal physical-corner indices | PASS | paired complete arrays and identical object order |
| 9 | 180-degree order reversal | PASS WITH CAPTURE CONTROL | both cameras are canonicalized before detection; stereo-pair visual QA remains mandatory |
| 10 | arbitrary stereo flags | PASS | only `CALIB_FIX_INTRINSIC`, documented above |
| 11 | rectification convention | PASS | non-empty ROIs and finite vertical disparity metrics |
| 12 | units | PASS | object/T/baseline in m; image diagnostics in pixel |

The item 9 control is important: rotating only one detected corner array after
detection is forbidden. The decoded image is first converted to its declared
canonical orientation, then both detectors see canonical pixels.

## Quality and WASS approval

The result includes mono RMS/K/D/per-view errors; stereo RMS/R/T/baseline/E/F;
and rectification matrices/ROIs/vertical disparity. `quality.py` may approve or
reject the unchanged OpenCV result but may not optimize it. The WASS exporter
requires `approved_for_wass=true`; otherwise it fails explicitly.

## Final mobile capture constraint

Calibration, static and wave recordings for both phones are one indivisible rig
session (six videos). Until all six videos are complete:

- do not remove either phone;
- do not move the support;
- do not reclamp either phone;
- do not change the relative camera pose.

Only after all six files are complete may the rig be dismantled and files be
uploaded. Any relative movement invalidates the shared extrinsics.

## Fallback boundary

If strict OpenCV calibration fails after capture, use only
`COARSE_GEOMETRY_VALIDATION`: `METROLOGICAL_VALIDITY=FALSE` and
`PURPOSE=ALGORITHM_CLOSURE_VALIDATION`. The fallback accepts measured,
user-specified, assumed, or derived geometry with field-level provenance. It
does not run WASS autocalibration by default; it exports a fixed R/T only after
explicit construction and review. It cannot support a centimetre-accuracy
claim.

The fallback is software-ready but intentionally has no pre-filled geometry:
the HomeTank_004 template accepts the required measurements and provenance,
the existing coarse intrinsic/pose models hold reviewed approximate K/R/T, and
the same fixed-calibration writer supplies WASS files without calling
autocalibrate. Matrix construction is not guessed from missing fields; it must
wait for the recorded HomeTank_004 measurements.
