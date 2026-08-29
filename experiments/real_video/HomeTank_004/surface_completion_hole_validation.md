# Continuous-hole MLS Validation on Frozen WASS Surfaces

Classification: `HOLE_COMPLETION_USABLE_FOR_DENSE_MVP`

## Scope and fixed method

This is an internal frozen-WASS surface-consistency test, not independent physical accuracy validation. For each selected observed center, every support point within a continuous circular hole is removed; the unchanged physical-X/Y Gaussian-weighted quadratic MLS predicts only the hidden center. The target is that center's frozen observed H.

No WASS run or reconstruction change occurred. Each source NPZ was read only after its frozen SHA-256 matched. Seed `20260829` selects 200 centers per frame and is reused at all four hole levels.

Hole radii are derived once from each frame's P90 nearest-neighbor spacing: `0.5×`, `1.5×`, `3.0×`, and `4.5× P90`. These represent near-single-point, small, medium and larger holes. The existing MLS support radius remains `6×P90`, Gaussian sigma `3×P90`, minimum support 12, maximum neighbors 64, and maximum condition number `1e8`. No radius or MLS parameter search was performed.

## Physical hole radii

| Frame | P90 spacing | hole_0 | hole_1 | hole_2 | hole_3 |
|---|---:|---:|---:|---:|---:|
| Static R0 | 0.102528 mm | 0.051264 mm | 0.153792 mm | 0.307583 mm | 0.461375 mm |
| Wave Case 1 | 0.100598 mm | 0.050299 mm | 0.150897 mm | 0.301793 mm | 0.452690 mm |
| Wave Case 2 | 0.097160 mm | 0.048580 mm | 0.145739 mm | 0.291479 mm | 0.437218 mm |

## Results

### Static R0

| Level | Coverage | MAE | RMSE | Median AE | P95 AE | Max AE | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|
| hole_0 | 100.0% | 0.470 mm | 1.242 mm | 0.079 mm | 2.244 mm | 9.939 mm | 0 |
| hole_1 | 100.0% | 0.544 mm | 1.338 mm | 0.121 mm | 2.614 mm | 9.872 mm | 0 |
| hole_2 | 100.0% | 0.516 mm | 1.128 mm | 0.144 mm | 2.128 mm | 6.230 mm | 0 |
| hole_3 | 99.5% | 0.805 mm | 1.683 mm | 0.246 mm | 3.526 mm | 9.939 mm | 1 |

### Wave Case 1

| Level | Coverage | MAE | RMSE | Median AE | P95 AE | Max AE | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|
| hole_0 | 99.5% | 0.325 mm | 0.704 mm | 0.036 mm | 1.642 mm | 3.736 mm | 1 |
| hole_1 | 99.0% | 0.374 mm | 0.788 mm | 0.068 mm | 1.699 mm | 4.122 mm | 2 |
| hole_2 | 99.0% | 0.422 mm | 0.958 mm | 0.099 mm | 1.749 mm | 7.643 mm | 2 |
| hole_3 | 97.0% | 0.559 mm | 1.160 mm | 0.193 mm | 2.022 mm | 8.499 mm | 6 |

### Wave Case 2

| Level | Coverage | MAE | RMSE | Median AE | P95 AE | Max AE | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|
| hole_0 | 99.0% | 0.152 mm | 0.338 mm | 0.033 mm | 0.726 mm | 1.942 mm | 2 |
| hole_1 | 99.0% | 0.178 mm | 0.376 mm | 0.041 mm | 0.783 mm | 1.883 mm | 2 |
| hole_2 | 99.0% | 0.191 mm | 0.435 mm | 0.055 mm | 0.699 mm | 3.131 mm | 2 |
| hole_3 | 98.0% | 0.310 mm | 0.762 mm | 0.091 mm | 1.563 mm | 6.800 mm | 4 |

## Decision

Error is not required to be monotonic, but the overall trend is clear: coverage declines modestly and upper-tail error generally grows at the largest hole. `hole_0` through `hole_2` pass the fixed continuation screen on all three frames: coverage ≥90%, RMSE ≤2 mm, and P95 absolute error ≤3 mm. At `hole_3`, Static P95 reaches 3.526 mm and all frames show more unsupported centers.

The maximum demonstrated practical level is therefore `hole_2`, corresponding to approximately `0.291–0.308 mm` radius in these datasets. The conclusion is `HOLE_COMPLETION_USABLE_FOR_DENSE_MVP`, with mandatory preservation of `UNSUPPORTED` and no claim that completed values equal true physical water height.

The next step may be a minimal dense height-map MVP: observed WASS points → MLS continuous surface → pixel query/dense H → `OBSERVED / ESTIMATED / UNSUPPORTED`. It is intentionally not implemented in this experiment.
