# Extended MLS Gap Validation

Classification: `NO_SAFE_EXTENSION`  
Coverage gain: `COVERAGE_GAIN_NOT_MATERIAL`

## Scope

This experiment extends the existing continuous-hole hold-out validation without changing its frozen WASS observations, seed (`20260829`), center selection, quadratic MLS weighting, minimum/maximum support, rank/condition gate, `6×P90` support radius, or `3×P90` Gaussian sigma. No WASS run, reconstruction change, dense-map regeneration, or parameter search occurred.

The target remains internal WASS-surface consistency: each originally observed center is hidden with all observations inside a physical circular hole, then predicted from observations outside that hole. It is not independent physical accuracy evidence.

## Trend including the previous boundary

All errors are millimetres. A dash means no prediction was supported.

### Static R0 — P90 spacing 0.102528 mm

| Gap | Radius | Coverage | MAE | RMSE | P95 |
|---:|---:|---:|---:|---:|---:|
| 3.0× | 0.307583 | 100.0% | 0.516 | 1.128 | 2.128 |
| 4.5× | 0.461375 | 99.5% | 0.805 | 1.683 | 3.526 |
| 6.0× | 0.615166 | 0.0% | — | — | — |
| 9.0× | 0.922749 | 0.0% | — | — | — |
| 12.0× | 1.230332 | 0.0% | — | — | — |

### Wave Case 1 — P90 spacing 0.100598 mm

| Gap | Radius | Coverage | MAE | RMSE | P95 |
|---:|---:|---:|---:|---:|---:|
| 3.0× | 0.301793 | 98.995% | 0.422 | 0.958 | 1.749 |
| 4.5× | 0.452690 | 96.985% | 0.559 | 1.160 | 2.022 |
| 6.0× | 0.603586 | 0.0% | — | — | — |
| 9.0× | 0.905379 | 0.0% | — | — | — |
| 12.0× | 1.207172 | 0.0% | — | — | — |

### Wave Case 2 — P90 spacing 0.097160 mm

| Gap | Radius | Coverage | MAE | RMSE | P95 |
|---:|---:|---:|---:|---:|---:|
| 3.0× | 0.291479 | 99.0% | 0.191 | 0.435 | 0.699 |
| 4.5× | 0.437218 | 98.0% | 0.310 | 0.762 | 1.563 |
| 6.0× | 0.582957 | 0.0% | — | — | — |
| 9.0× | 0.874436 | 0.0% | — | — | — |
| 12.0× | 1.165915 | 0.0% | — | — | — |

## Decision

`3×P90` remains the maximum SAFE range under the existing screen (coverage ≥90%, RMSE ≤2 mm, P95 ≤3 mm on every dataset). `4.5×P90` is a TRANSITION range: coverage remains high, but Static R0 P95 reaches 3.526 mm and fails the common screen. At `6×P90`, the artificial hole equals the unchanged MLS support radius, so the strict “outside hole and inside support radius” rule leaves no support observations; 9× and 12× also remain unsupported.

Therefore no larger high-confidence or low-confidence production interval is justified. The formal dense policy stays at `3×P90`; no new status is introduced, Case 2 is not regenerated, and `(799,396)` remains `UNSUPPORTED`. The preserved demo coverage is 5.3599% OBSERVED, 0.0220% ESTIMATED, 94.6181% UNSUPPORTED, and 5.3819% valid H.
