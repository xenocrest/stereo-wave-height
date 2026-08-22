# HomeTank_004 plane RANSAC valid-point sampling update

## Original failure

Candidate A reached rectification, dense stereo and triangulation, but upstream
WASS plane RANSAC returned zero inliers. The retained component occupied only
8.0816% of the full 1920 x 1080 pixel mesh. Sampling three pixels uniformly
from that full mesh gave approximately 80.96% probability of proposing no
all-valid triplet in 400 frozen rounds, even though offline analysis found a
2.249 mm RMS plane.

## Controlled plane-extraction change

The new `VALID_POINT_SAMPLING` mode first builds a list of indices whose XYZ
point is already marked valid, then randomly selects three entries from that
list. It retains the original minimum pixel-separation check, three-point plane
model, point-to-plane distance calculation, strict `<` comparison, distance
threshold `1.0`, and 400 rounds.

The original `FULL_IMAGE_RANDOM_SAMPLING` remains the default. Its candidate
selection and final `NPTS/10` acceptance population are unchanged. In valid
mode, the same 10% final acceptance rule uses the valid population as its
denominator; otherwise a component smaller than 10% of the full image could
never pass even with every valid point classified as an inlier.

This change is confined to plane extraction. It does not modify calibration,
`K/D/R/T`, rectification policy, matching, dense stereo, triangulation, Z-gap
clustering, or point-to-plane inlier judgment.

## HomeTank_004 frozen run

The three previously timestamp-paired static workdirs were reused. Candidate A
remained `FULL_CALIBRATION`; rectification remained `alpha=0.0` with
`CALIB_ZERO_DISPARITY`; autocalibration and wave were not run.

| Frame | Triangulated | Largest component | Best inliers | Inlier ratio | Plane RMS | Stereo |
|---|---:|---:|---:|---:|---:|---|
| 000000 | 216,874 | 167,581 | 167,581 | 1.0000 | 2.2491 mm | PASS |
| 000001 | 133,968 | 33,286 | 33,286 | 1.0000 | 2.1611 mm | PASS |
| 000002 | 141,950 | 34,411 | 34,411 | 1.0000 | 2.0065 mm | PASS |

All three runs generated `mesh_cam.xyzC`. Plane RMS is the orthogonal residual
of the pre-alignment `mesh_full.ply` points against WASS's refined plane, with
baseline-normalized distances converted using the unchanged OpenCV
`||T||=0.06868471158474378 m`.

The fitted camera-coordinate `z=ax+by+c` coefficients are:

| Frame | a | b | c (m) | mean signed residual | maximum absolute residual |
|---|---:|---:|---:|---:|---:|
| 000000 | 0.4604331984 | 0.0784329395 | 0.3971745173 | -0.0137 mm | 74.2757 mm |
| 000001 | 0.3409947789 | 0.0361078488 | 0.3878047532 | -0.0126 mm | 33.0415 mm |
| 000002 | 0.5856541884 | -0.0393184049 | 0.4008669322 | -0.0100 mm | 11.9686 mm |

## Result and limitations

`water_plane_status=STATIC_WATER_PLANE_DETECTED`: every frame has nonzero best
inliers, WASS completes plane refinement, RMS is 2.01--2.25 mm, and XYZ output
exists. This is an algorithm-path result, not metrological calibration
approval. The isolated runtime uses the frozen modular OpenCV 4.6 DLLs, but its
compiler-level numerical equivalence to the production build is still
`NOT_ESTABLISHED`.

Historical status remains `CALIBRATION_QUALITY_FAIL` and
`approved_for_wass=false`. No wave result was generated. The next step should
validate static XYZ physical scale and inter-frame plane consistency before
considering any wave processing.
