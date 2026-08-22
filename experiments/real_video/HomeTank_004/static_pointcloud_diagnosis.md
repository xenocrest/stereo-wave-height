# HomeTank_004 static point-cloud diagnosis before plane RANSAC

## Scope and frozen inputs

This diagnosis uses Candidate A `FULL_CALIBRATION`, unchanged OpenCV
`K0/D0/K1/D1/R/T`, and the frozen rectification policy `alpha=0.0`,
`zero_disparity=true`. Matching, dense stereo, triangulation, Z-gap clustering,
and all plane-RANSAC parameters are unchanged. Wave data were not run.

The isolated WASS 1.11 build uses commit `6b82aeb...` and the frozen modular
OpenCV 4.6 DLL set. Numerical equivalence to the production compiler build is
still `NOT_ESTABLISHED`, so the result is diagnostic. The external run is at
`D:/stereo-wave-height-runs/HomeTank_004/static-full-calibration-policy-a0-raw-pointcloud-20260822`.

## Triangulation and export

WASS reported 216,874 valid triangulated points. Its existing
`SAVE_FULL_MESH=true` diagnostic output was enabled without changing numerical
processing. After the unchanged 99th-percentile Z-gap clustering, the largest
component contained 167,581 points and was written as binary little-endian
`mesh_full.ply` immediately before WASS plane RANSAC. No `mesh_cam.xyzC` exists
because RANSAC subsequently failed.

WASS runs with camera distance normalized to one baseline. Candidate A's
unchanged OpenCV translation has `||T||=0.06868471158474378 m`; exported XYZ
was multiplied by this value to report metres. The manual baseline was not
used.

## XYZ and depth statistics

All 167,581 exported points are finite.

| Quantity | Minimum (m) | Maximum (m) |
|---|---:|---:|
| X | -0.096170033 | -0.058158568 |
| Y | -0.094909840 | +0.008289802 |
| Z | 0.346059589 | 0.443243704 |

Largest-component Z percentiles are:

| P1 | P5 | P50/median | P95 | P99 |
|---:|---:|---:|---:|---:|
| 0.350281680 m | 0.353300110 m | 0.361283007 m | 0.368520744 m | 0.370198409 m |

The pre-cluster depth diagnostic contains all 216,874 triangulated depths.
Its P1/P5/P50/P95/P99 are respectively 0.347621872, 0.352999201,
0.362459038, 0.848301837, and 6.774361124 m, with range
0.318359938--12.851817784 m. Thus triangulation includes a long positive-depth
outlier tail, while official Z-gap largest-component extraction retains
77.2711% of triangulated points and isolates the concentrated near surface.

## Offline plane candidates

These fits are diagnostic only and do not replace or tune WASS RANSAC.
Vertical residuals use `z=ax+by+c`; orthogonal residuals use a normalized plane
`n dot X + d = 0`.

| Point set | N | z-plane `(a,b,c)` | vertical RMS | orthogonal RMS | maximum orthogonal residual |
|---|---:|---|---:|---:|---:|
| all exported XYZ | 167,581 | `(0.416576870, 0.078966265, 0.394076674)` | 2.4616 mm | 2.2490 mm | 74.2961 mm |
| central Z P5--P95 | 150,823 | `(0.365802331, 0.069955732, 0.390151153)` | 1.9198 mm | 1.7906 mm | 12.3098 mm |
| maximum connected component | 167,581 | same as all exported XYZ | 2.4616 mm | 2.2490 mm | 74.2961 mm |

The `all exported XYZ` and `maximum connected component` rows are identical by
construction: official `SAVE_FULL_MESH` is called after largest-component
extraction and immediately before plane RANSAC. Pre-cluster export contains Z
and validity but not complete XYZ, so no untraceable triangulation was invented
to manufacture a separate all-precluster plane fit.

The all-component normalized orthogonal plane is
`n=(-0.417080848,-0.070964883,0.906094670)`, `d=-0.359851650 m`.
Its median/P90/P95/P99 absolute orthogonal residuals are
0.7644/2.2661/3.2455/9.3529 mm. This is direct evidence that a dominant plane is
present despite a small outlier tail.

## Why WASS returned zero inliers

Source inspection shows that `PovMesh::ransac_find_plane` samples three pixel
coordinates uniformly over the full `1920 x 1080` mesh and rejects a round if
any sampled point is invalid. It does not sample directly from the valid-point
list. The retained component occupies only:

`167581 / (1920*1080) = 0.08081645` (8.0816%).

Ignoring the additional minimum-separation constraint, the probability that
one round draws three valid pixels is therefore `0.08081645^3 = 0.000527836`.
For 400 frozen rounds, the expected number of usable triplets is only 0.2111
and the probability of drawing none is approximately 80.9620%. The observed
`best inliers=0` is therefore quantitatively consistent with no valid triplet
ever being proposed; it is not evidence that the distance threshold rejected
the fitted plane.

## Classification and next step

Classification: **PLANE_PRESENT_BUT_RANSAC_TOO_STRICT**, specifically
`RANSAC_VALID_TRIPLET_SAMPLING_INSUFFICIENT_FOR_SPARSE_IMAGE_SUPPORT`.
“Too strict” here does not mean the frozen distance threshold is too small; it
means the full-image uniform sampling policy provides too few valid hypotheses.
`PLANE_NOT_PRESENT` and `POINT_CLOUD_GEOMETRY_INVALID` are rejected by the
finite concentrated component and 2.249 mm orthogonal plane RMS.

The next step should be a design review of an upstream-compatible way to sample
valid points (or otherwise guarantee enough valid hypotheses) while keeping
the metric threshold frozen. No RANSAC parameter, calibration value, or
rectification policy was changed in this diagnosis. Wave remains prohibited.
`CALIBRATION_QUALITY_FAIL` and `approved_for_wass=false` remain unchanged.
