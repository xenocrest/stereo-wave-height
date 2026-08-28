# Frozen WASS Spatial Surface-completion Hold-out Validation

Classification: `SPATIAL_SURFACE_COMPLETION_PROMISING`

## Scope

This is an internal hold-out reconstruction-consistency experiment. The targets called “truth” below are frozen WASS-observed heights, not independent physical truth. The experiment tests whether a continuous local surface can reproduce existing WASS samples; it does not establish real water-height accuracy and does not estimate the unsupported Case 2 ruler click.

No WASS run or reconstruction change occurred. The three frozen height NPZ files were accepted only after their SHA-256 matched the recorded Static R0, Wave Case 1 and Wave Case 2 baselines.

## Fixed method

For every held-out point, the method fits one Gaussian-weighted quadratic in physical coordinates:

`H(X,Y) = aX² + bXY + cY² + dX + eY + f`.

Coordinates are centered at the query and normalized by the support radius before solving. The radius is `6 × frame P90 nearest-neighbor spacing`, and Gaussian sigma is `3 × P90`; thus no absolute distance was guessed. At least 12 points are required, at most the nearest 64 are used, numerical rank must be 6, and weighted design condition number must not exceed `1e8`. Unsupported or ill-conditioned queries return NaN.

The deterministic hold-out uses seed `20260828`, ratio `0.5%`, capped at 1,000 points. Every test index is removed from the support tree before prediction. Original arrays are read-only and unchanged.

## Results

| Frozen frame | Tests | Supported | Coverage | MAE | RMSE | Median AE | P95 AE | Max AE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Static R0 | 837 | 835 | 99.761% | 0.450 mm | 1.061 mm | 0.101 mm | 1.956 mm | 9.319 mm |
| Wave Case 1 | 434 | 433 | 99.770% | 0.361 mm | 0.803 mm | 0.079 mm | 1.469 mm | 5.563 mm |
| Wave Case 2 | 177 | 177 | 100.000% | 0.204 mm | 0.427 mm | 0.042 mm | 0.893 mm | 2.641 mm |

Only three queries were unsupported, all because fewer than 12 points fell inside the derived radius: two Static and one Wave Case 1. No query was rejected as ill-conditioned.

## Physical spacing and support strata

Frame P90 nearest-neighbor spacing is approximately `0.097–0.103 mm`, producing radii `0.583–0.615 mm` and Gaussian sigma `0.291–0.308 mm`. Query-to-remaining-support distance is divided using the frame's original spacing distribution: near `≤P50`, medium `(P50,P90]`, and sparse `>P90`.

| Frame | Near P95 AE | Medium P95 AE | Sparse P95 AE | Sparse coverage |
|---|---:|---:|---:|---:|
| Static R0 | 3.149 mm | 0.401 mm | 0.730 mm | 97.727% |
| Wave Case 1 | 2.517 mm | 0.235 mm | 0.674 mm | 97.436% |
| Wave Case 2 | 1.323 mm | 0.208 mm | 0.339 mm | 100.000% |

Error does **not** increase monotonically with nearest-support distance. The near stratum is worse in all three frames, so distance alone is not a sufficient confidence measure; local curvature, boundaries or frozen reconstruction outliers also matter. Sparse coverage remains high in this hold-out sample, but the three minimum-support failures confirm that a coverage gate is still required.

## Decision

All frames exceed 99.7% coverage, RMSE is `0.427–1.061 mm`, and P95 absolute error is `0.893–1.956 mm`. This passes the predefined continuation screen (coverage ≥95%, RMSE ≤2 mm, P95 ≤3 mm), which is a research decision rule rather than a physical-accuracy acceptance criterion.

The result is therefore `SPATIAL_SURFACE_COMPLETION_PROMISING`. Local physical-coordinate MLS is technically worth continued study, but maximum errors of `2.64–9.32 mm` and the non-monotonic strata behavior prohibit treating it as an unconditional dense measurement method. No dense map, ray/surface intersection, Case 2 ruler estimate, temporal completion or additional algorithm is developed here.
