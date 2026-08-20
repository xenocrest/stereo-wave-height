# HomeTank_003 checkerboard detection diagnosis

## Scope and frozen status

This is a small visual/detector diagnosis only. It does not repeat the complete
dataset scan, run calibration, change the existing
`CALIBRATION_DATASET_INSUFFICIENT` classification, process static/wave, or call
WASS. Diagnostic images and detailed per-attempt JSON remain outside Git under
`D:\research\stereo-wave-height-data\HomeTank_003\checkerboard_diagnostics`.

## Representative frames

Both calibration videos were inspected at 0, 1, 5, 15, 30, 45, 60, 69, 90,
110, 126, and 134 s. These cover early/middle/late, near/far, frontal,
in-plane rotation, and projectively tilted views.

| Time (s) | Cam0 sharpness | Cam0 SB 0.5x raw/canonical | Cam1 sharpness | Cam1 SB finite fallback |
|---:|---:|---|---:|---|
| 0 | 220.7 | PASS / FAIL | 163.8 | PASS |
| 1 | 178.3 | PASS / FAIL | 218.8 | PASS |
| 5 | 59.0 | PASS / PASS | 171.8 | PASS |
| 15 | 47.9 | FAIL / FAIL | 346.5 | FAIL |
| 30 | 67.2 | PASS / FAIL | 224.7 | PASS |
| 45 | 131.0 | PASS / FAIL | 237.1 | PASS |
| 60 | 92.2 | FAIL / FAIL | 435.5 | FAIL |
| 69 | 62.0 | PASS / PASS | 124.6 | PASS |
| 90 | 69.0 | FAIL / FAIL | 289.8 | PASS |
| 110 | 76.6 | FAIL / PASS | 228.8 | FAIL |
| 126 | 92.5 | PASS / FAIL | 106.5 | PASS |
| 134 | 182.3 | FAIL / FAIL | 261.1 | PASS |

The lossless raw/canonical comparison is used for the rotation column. A
separate JPEG diagnostic sometimes changes a marginal SB decision, which is
additional evidence of detector instability rather than a geometric change.

Visually strongest examples are cam0 45/69/134 s and cam1 30/45/90 s. Cam0
15 s is soft and close to clipping; 60 s is tilted with visible target
non-planarity; 110/126 s have adverse portrait/far framing.

## Target topology and image geometry

The target is an alternating checkerboard in topology: 10 x 7 physical cells
produce 9 x 6 internal intersections. No image evidence supports a different
pattern size, so no neighbouring pattern-size search was performed.

The dark cells are not uniformly printed black. They are hand-shaded grey with
strong within-cell pencil texture, uneven boundaries, and varying contrast.
The backing also bends in several poses. These facts matter to both detection
and any later planar calibration, even when all 54 corners are found.

For successful cam1 frames, median adjacent internal-grid spacing ranges from
50.4 to 103.0 px. The measured internal-corner bounding-box fraction ranges
from 0.0774 to 0.2710. Extrapolating only for a rough physical-board coverage
estimate by `(10/8)*(7/5)` gives approximately 13.5% to 47.4% of the image.
Thus the board is not generally below a usable pixel size. Exact internal
bounds and spacing are retained in the external diagnostics JSON.

Near-black/near-white saturation averages 0.0269% for cam0 and 0.0016% for
cam1. No representative frame shows glare severe enough to explain the
failure. Cam0 Laplacian-variance sharpness has mean 106.6 and median 84.4,
versus cam1 mean 234.1 and median 226.7. Cam0 is therefore materially softer
in many matched poses; motion/focus softness is a secondary causal factor.

Clipping and perspective explain individual failures, especially close or
strongly tilted views, but not the global native-resolution result: clear,
fully visible views also fail at 1x and recover at 0.5x.

## Detector experiment

Each representative frame was tested with:

- `findChessboardCornersSB` and the project flags;
- classic `findChessboardCorners`;
- raw grayscale and CLAHE;
- 0.5x, 1x, and 1.5x image scale.

Classic detection returned no complete pattern in any representative
combination. Native 1x SB was also almost always unsuccessful: among these
frames only cam1 at 0 s passed at 1x. In contrast, 0.5x SB recovered 7/12 cam0
raw frames and 9/12 cam1 frames. CLAHE helps some marginal frames but is not a
universal fix. Increasing to 1.5x does not help.

This scale response shows that the original cam0 `0/270` result primarily
describes the frozen native-resolution detector path; it does not prove that
the physical 54-corner lattice is absent.

## Cam0 orientation audit

Cam0 contains a -180-degree Display Matrix. Lossless BMP decoding proves that
`rotate180(raw)` and FFmpeg's canonical output are pixel-identical for all 12
timestamps: mean and maximum absolute pixel differences are both zero. There
is no crop, second rotation, mirror, or abnormal resize in the canonical
transform.

Nevertheless, OpenCV SB is not decision-invariant to a 180-degree rotation on
these marginal hand-made patterns: at 0.5x, the raw orientation passes 7/12
while canonical passes 3/12 in the lossless test. Because the pixel transform
is exact, this is detector orientation sensitivity, not an orientation
pipeline error. A future implementation may detect in both orientations and
map points into canonical coordinates, but ordering must then be explicitly
verified before calibration.

No mirrored topology is visible. Digital stabilization cannot be proven or
excluded from this small sample, but there is no observed discontinuous crop
or aspect-ratio change that explains the detector failure.

## Root-cause ranking

1. **DETECTOR_LIMITATION** — decisive scale and orientation sensitivity of SB
   on this marginal high-resolution target; classic fails completely.
2. **LOW_CONTRAST / NONUNIFORM_TARGET_APPEARANCE** — hand-shaded grey cells,
   internal pencil texture, rough borders, and nonuniform contrast violate the
   clean printed-checkerboard appearance expected by standard detectors.
3. **CAM0_IMAGE_SOFTNESS / MOTION_BLUR** — cam0 sharpness is substantially
   lower than cam1 at many corresponding times, reducing boundary stability.
4. **PERSPECTIVE / CLIPPING / TARGET_BENDING** — explains particular poses and
   is a later planar-calibration risk, but cannot explain all failures.

`WRONG_PATTERN_TOPOLOGY`, `BOARD_TOO_SMALL`, `GLARE`, and
`CAM0_ORIENTATION_PIPELINE_ERROR` are not supported as primary causes.

## Minimum remedy

For software diagnosis, add one reviewed fallback only: when native SB fails,
try SB at 0.5x (optionally one CLAHE branch), rescale all 54 points to canonical
pixels, refine there, and preserve complete-pattern/quality gates. This must be
tested before changing the formal HomeTank_003 assessment; it is not applied
in this report.

For reliable new calibration, reprinting is strongly recommended: use a
machine-printed, high-contrast, rigid and flat 10 x 7 board with verified 20 mm
cells. First require bilateral 54/54 on a short preflight. Cam0 focus/exposure
and motion stability should be improved before recording the full sequence.

Only calibration needs supplementation if the camera rig is independently
confirmed unchanged between the old calibration and existing static/wave
videos. That fact remains `UNKNOWN`. If either camera must be moved to capture
the replacement calibration, the existing static/wave cannot use the new
extrinsics. The files therefore retain evidentiary value, but their future
reconstruction value is conditional on resolving rig stability.
