# HomeTank_004 WASS SGBM Matching Parameter Audit

## 1. Frozen scope

This two-stage audit uses Candidate A, the unchanged OpenCV `K/D/R/T`,
rectification `alpha=0` plus zero disparity, `numberOfDisparities=640`, and
`VALID_POINT_SAMPLING`. It changes no formal experiment configuration and does
not process wave data.

Runs are isolated outside Git at
`D:/stereo-wave-height-runs/HomeTank_004/sgbm-parameter-audit-20260822`.
Every WASS process returned code 0. Historical statuses remain
`STATIC_VALIDATION_FAIL`, `CALIBRATION_QUALITY_FAIL`, and
`approved_for_wass=false`.

## 2. Baseline and staged matrix

The frozen matcher is OpenCV StereoSGBM with uniqueness `1`, block size `13`,
minimum disparity `1`, number of disparities `640`, speckle range `16`, speckle
window `-70`, prefilter cap `60`, and `disp12MaxDiff=-1`. WASS derives
`P1=2*block^2` and `P2=64*block^2`.

The matrix deliberately avoids a Cartesian search:

1. Stage 1 fixes block size 13 and tests uniqueness `1, 5, 10, 15`.
2. According to the predeclared priority—cross-frame Z consistency, then plane
   RMS, then point count—Stage 1 selects uniqueness 15.
3. Stage 2 fixes uniqueness 15 and tests block size `7, 11, 15, 21`.

Changing block size necessarily changes WASS's derived SGBM smoothness
penalties: P1/P2 are 98/3136, 242/7744, 450/14400, and 882/28224 for blocks
7, 11, 15, and 21. Their multipliers are unchanged.

As in the disparity-range audit, the lossless float disparity is not exported.
Reported values are effective rectified disparities reconstructed from valid
`precluster_depth.bin` samples with the same fixed geometry.

## 3. Stage 1: uniqueness ratio at block 13

| U | Frame | Valid disparity | Mean d | Median d | P5 d | P95 d | Retained XYZ | Median Z (m) | Plane RMS (mm) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 000000 | 216,874 | 585.272 | 639.546 | 262.498 | 640.559 | 167,581 | 0.290216 | 2.249 |
| 1 | 000001 | 133,968 | 488.817 | 629.629 | 48.483 | 640.554 | 33,286 | 0.330105 | 2.161 |
| 1 | 000002 | 141,950 | 478.108 | 627.580 | 58.623 | 640.554 | 34,411 | 0.233335 | 2.007 |
| 5 | 000000 | 118,000 | 622.219 | 640.547 | 500.464 | 640.559 | 95,094 | 0.256754 | 0.704 |
| 5 | 000001 | 47,926 | 567.828 | 640.540 | 112.297 | 640.557 | 19,817 | 0.295055 | 0.777 |
| 5 | 000002 | 51,144 | 556.952 | 638.245 | 97.734 | 640.556 | 18,479 | 0.270775 | 0.858 |
| 10 | 000000 | 70,509 | 636.335 | 640.550 | 636.555 | 640.558 | 52,713 | 0.243624 | 0.289 |
| 10 | 000001 | 24,053 | 620.322 | 640.547 | 626.715 | 640.556 | 13,841 | 0.276472 | 0.453 |
| 10 | 000002 | 21,346 | 612.605 | 640.546 | 381.425 | 640.557 | 9,928 | 0.256011 | 0.522 |
| 15 | 000000 | 46,905 | 639.504 | 640.551 | 638.925 | 640.558 | 16,612 | 0.237813 | 0.213 |
| 15 | 000001 | 15,293 | 637.641 | 640.548 | 637.363 | 640.556 | 10,174 | 0.265344 | 0.390 |
| 15 | 000002 | 11,472 | 633.511 | 640.548 | 631.284 | 640.557 | 5,102 | 0.243714 | 0.230 |

| Uniqueness | Median-Z range (mm) | Maximum normal variation | Mean / max RMS (mm) | Total valid disparity |
|---:|---:|---:|---:|---:|
| 1 | 96.769 | 12.166 deg | 2.139 / 2.249 | 492,792 |
| 5 | 38.301 | 4.636 deg | 0.780 / 0.858 | 217,070 |
| 10 | 32.847 | 4.070 deg | 0.421 / 0.522 | 115,908 |
| 15 | 27.532 | 3.070 deg | 0.278 / 0.390 | 73,670 |

Uniqueness 15 wins the declared numerical ordering, but this improvement is
obtained by rejecting 85.1% of baseline valid disparity samples. Its accepted
distribution is also concentrated at the 640-pixel search boundary. It is a
stage-selection result, not validation of physical correctness.

## 4. Stage 2: block size at uniqueness 15

| Block | Frame | Valid disparity | Mean d | Median d | P5 d | P95 d | Retained XYZ | Median Z (m) | Plane RMS (mm) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 000000 | 23,765 | 638.601 | 640.550 | 636.303 | 640.557 | 7,190 | 0.248110 | 0.258 |
| 7 | 000001 | 7,051 | 637.001 | 640.547 | 637.294 | 640.555 | 3,585 | 0.262069 | 0.377 |
| 7 | 000002 | 5,862 | 629.640 | 640.543 | 630.471 | 640.554 | 3,160 | 0.292112 | 0.578 |
| 11 | 000000 | 39,758 | 638.469 | 640.550 | 637.606 | 640.557 | 14,302 | 0.237860 | 0.234 |
| 11 | 000001 | 13,394 | 632.023 | 640.548 | 635.308 | 640.555 | 8,965 | 0.268884 | 0.430 |
| 11 | 000002 | 9,831 | 635.123 | 640.547 | 631.472 | 640.556 | 4,580 | 0.242765 | 0.247 |
| 15 | 000000 | 53,151 | 639.892 | 640.551 | 639.364 | 640.558 | 42,039 | 0.240948 | 0.170 |
| 15 | 000001 | 16,656 | 637.138 | 640.548 | 637.238 | 640.556 | 10,877 | 0.263923 | 0.373 |
| 15 | 000002 | 12,423 | 633.694 | 640.548 | 631.284 | 640.557 | 5,164 | 0.245478 | 0.202 |
| 21 | 000000 | 93,841 | 233.170 | 215.679 | 36.783 | 634.100 | 43,829 | -0.894429 | 11.869 |
| 21 | 000001 | 118,621 | 295.818 | 201.917 | 34.842 | 637.238 | 41,583 | -1.393190 | 19.907 |
| 21 | 000002 | 106,526 | 273.382 | 117.735 | 30.714 | 635.980 | 20,403 | -2.478078 | 11.840 |

| Block | Median-Z range (mm) | Maximum normal variation | Mean / max RMS (mm) | Total valid disparity |
|---:|---:|---:|---:|---:|
| 7 | 44.002 | 5.945 deg | 0.404 / 0.578 | 36,678 |
| 11 | 31.024 | 3.445 deg | 0.304 / 0.430 | 62,983 |
| 15 | 22.975 | 2.801 deg | 0.248 / 0.373 | 82,230 |
| 21 | 1583.648 | 9.546 deg | 14.539 / 19.907 | 318,988 |

Block 15 is the best observed Stage-2 setting under the declared priorities.
Block 21 reconstructs negative-Z components and is physically invalid.

## 5. Decision

The best observed diagnostic pair is `uniqueness=15, block=15`, with per-frame
median Z `0.240948`, `0.263923`, and `0.245478 m`, a `22.975 mm` range, maximum
normal variation `2.801 deg`, and RMS `0.170`, `0.373`, and `0.202 mm`.

It does **not** restore static validation:

- 22.975 mm inter-frame depth spread remains too large for a stable reference;
- the accepted P5/median/P95 disparities remain overwhelmingly near the
  640-pixel upper bound;
- the strict uniqueness setting rejects most observations, so small plane RMS
  may describe a narrow boundary-clipped subset rather than the full water
  surface.

Conclusion: SGBM uniqueness and block size strongly affect which component is
retained, but this matrix yields **no validated formal parameter change**.
`STATIC_VALIDATION_FAIL` remains. The next diagnostic should examine rectified
image scale/homography drift and common texture support; changing SGBM again
before resolving the range-boundary/input-geometry interaction is not
justified. Wave remains prohibited.

The isolated executable exactly reproduces the frozen uniqueness-1/block-13
control, but compiler-level equivalence to the old production executable
remains `NOT_ESTABLISHED`.
