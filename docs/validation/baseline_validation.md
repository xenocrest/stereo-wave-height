# 双目基线单因素验证

## 目的与边界

This pre-purchase ideal-pinhole experiment fixes the scene distance at 2.00 m and changes only stereo baseline. It asks how disparity, common field of view, WASS support, and recovered height change. It does not search for a magical optimum, select purchased hardware, or establish real-water accuracy.

All groups freeze the 2448 x 2048 candidate camera, 3.45 um pitch, nominal 8 mm lens (`f_px=2318.8405797 px`), zero distortion, `A=0.030 m`, `lambda=0.80 m`, `f=0.50 Hz`, two independent static plus ten dynamic frames, deterministic texture/timestamps, matcher/stereo configuration, `ZGAP_PERCENTILE=99.5`, official 160 x 160 DCT grid at 0.01 m, and acceptance gates. WASS and wassgridsurface were not modified.

## 物理模型及其与工作距离的耦合

Baseline is the separation of the two virtual camera centres. For rectified pinhole stereo,

$$
d=\frac{f_{px}B}{Z}, \qquad \left|\frac{\partial Z}{\partial d}\right|=\frac{Z^2}{f_{px}B}.
$$

At fixed distance, disparity grows linearly and one-pixel depth sensitivity improves inversely with baseline. The conservative horizontal overlap estimate is

$$
W_{common}=\frac{(N_x-d)(Z-A)}{f_{px}}=\frac{N_x(Z-A)}{f_{px}}-B.
$$

The central parallel-rig ray angle reuses the established Case 0 expression

$$
\theta=2\arctan\left(\frac{B}{2Z}\right).
$$

Increasing baseline therefore improves ideal triangulation conditioning while reducing overlap and potentially increasing appearance/occlusion differences. Baseline and distance are coupled through the ratio $B/Z$; neither can be selected independently from the intended field of view.

## 候选范围与冻结选择

The WASS disparity interval is 160--320 px, required physical grid width is 1.59 m, and `TRIANG_MIN_ANGLE=3 deg`.

| B | nominal d | +/-30 mm d range | sensitivity | common width | ray angle | eligible |
|---:|---:|---:|---:|---:|---:|---|
| 0.10 m | 115.942 px | 114.229--117.708 px | 17.250 mm/px | 1.980 m | 2.864 deg | no: disparity and angle |
| 0.15 m | 173.913 px | 171.343--176.561 px | 11.500 mm/px | 1.930 m | 4.295 deg | yes, B1 |
| 0.20 m | 231.884 px | 228.457--235.415 px | 8.625 mm/px | 1.880 m | 5.725 deg | yes, B0 |
| 0.25 m | 289.855 px | 285.571--294.269 px | 6.900 mm/px | 1.830 m | 7.153 deg | yes, B2 |
| 0.30 m | 347.826 px | 342.686--353.123 px | 5.750 mm/px | 1.780 m | 8.578 deg | no: disparity |

B1=0.15 m and B2=0.25 m were frozen before rendering. B0=0.20 m reuses exact G1/D0 evidence because all frozen factors match.

## 坐标与固定点规程

The virtual camera centres are at $X_w=-B/2$ and $+B/2$. The B0 mapping `x_world=x_grid+0.10 m` therefore generalizes explicitly as `x_world=x_grid+B/2`: offsets are 0.075, 0.100, and 0.125 m. Holding 0.10 m fixed would create artificial phase errors of approximately +/-0.19635 rad; no inferred post-result translation is used.

Preflight found that prior point P5 `(-0.795,0.695) m` lies outside B2's physical grid domain. It is excluded without replacement and recorded as a protocol deviation. The preregistered, jointly visible P1--P4 are used for cross-baseline spatial comparison; no point was chosen from its error result.

## WASS 执行状态

| stage | B1 | B0 | B2 |
|---|---|---|---|
| prepare | 12/12 PASS | reused PASS | 12/12 PASS |
| match | 12/12 PASS | reused PASS | 12/12 PASS |
| autocalibrate | PASS | reused PASS | PASS |
| subset | dynamic `000002..000011` | same | dynamic `000002..000011` |
| stereo | 12/12 PASS | reused PASS | 12/12 PASS |
| official grid | PASS | reused PASS | PASS |

The first B1 grid setup attempt failed only because the project run script wrote each four-element plane as four rows. The exact same WASS planes were reorganized to the official one-frame-per-row `planes.txt` schema; retry passed. No numerical result or parameter was changed.

## 支持域与高度结果

| metric | B1 0.15 m | B0 0.20 m | B2 0.25 m |
|---|---:|---:|---:|
| triangulated min/mean/max | 4,435,893 / 4,461,189 / 4,470,428 | 4,324,706 / 4,347,761 / 4,358,632 | 4,206,746 / 4,229,633 / 4,242,180 |
| largest component min/mean/max | 4,435,505 / 4,455,981 / 4,466,517 | 4,323,792 / 4,344,854 / 4,358,006 | 4,204,862 / 4,227,395 / 4,240,646 |
| retention min/mean/max | 99.699% / 99.883% / 99.998% | 99.845% / 99.933% / 99.986% | 99.911% / 99.947% / 99.969% |
| raw support min/mean/max | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% |
| finite coverage / hole rate | 100% / 0% | 100% / 0% | 100% / 0% |
| signed bias | -0.569 mm | -0.433 mm | -0.335 mm |
| RMSE | 1.483 mm | 1.030 mm | 0.906 mm |
| MAE | 1.205 mm | 0.849 mm | 0.743 mm |
| max absolute error | 5.048 mm | 3.398 mm | 3.094 mm |
| P50 / P90 | 1.091 / 2.380 mm | 0.762 / 1.679 mm | 0.666 / 1.476 mm |
| P95 / P99 | 2.803 / 3.588 mm | 1.949 / 2.422 mm | 1.712 / 2.103 mm |
| result | **PASS** | **PASS** | **PASS** |

All groups pass RMSE/MAE <=10 mm, max <=30 mm, raw support >=95%, and hole rate <=5%. Triangulated count decreases as baseline grows, consistent with reduced overlap, while retained fraction remains above 99.69% and raw grid support stays complete.

## 波参数与局部空间结果

| metric | B1 | B0 | B2 |
|---|---:|---:|---:|
| recovered A | 29.587 mm | 29.596 mm | 29.695 mm |
| A error | -0.413 mm | -0.404 mm | -0.305 mm |
| recovered lambda / error | 0.800 m / <1e-12 m | same | same |
| recovered f / error | 0.500 Hz / 0 Hz | same | same |
| phase error | +0.000761 rad | +0.000406 rad | +0.000003 rad |
| shared-point bias range | -1.370 to +0.354 mm | -0.244 to +0.320 mm | +0.038 to +0.329 mm |

For the shared P1--P4 points, B1 has the largest local spread; B2 is smallest and uniformly slightly positive. The global height metrics improve in the theoretical direction B1 -> B0 -> B2. This is evidence for this frozen synthetic scene only, not a universal monotonic law or proof that larger is always better.

## 工作距离与基线的联合解释

The experiments provide two cross-sections of the unknown valid deployment set $(B,Z)\in\Omega_{valid}$: distance at B=0.20 m and baseline at Z=2.00 m. They do not constitute a two-dimensional scan. D0/B0 passes at `(0.20,2.00)`. At fixed B=0.20 m, 1.75 m failed raw-support and 2.50 m stopped at plane fit. At fixed Z=2.00 m, all three tested baselines pass.

B2 at 2.00 m passes and theory predicts that `(B=0.25 m,Z=2.50 m)` restores nominal disparity to 231.884 px, equal to D0/B0, while sensitivity would be 10.781 mm/px. This is a justified single future cross-check candidate for the prior far-distance blocker. It is only recommended; it was not run. The alternative small-baseline/near-distance direction improves overlap but lowers disparity and has no equally direct explanation of D1's single-frame support collapse.

## 结论、限制与待办

- B1, B0, and B2 all pass at Z=2.00 m. B2 has the best measured errors in this bounded ideal-synthetic test, but no final optimal baseline is selected.
- The theoretical sensitivity trend agrees with measured global error; the reduced triangulated count captures the competing overlap cost.
- The two validated cross-sections are preliminary deployment geometry evidence, not a complete valid region.
- A single `(0.25 m,2.50 m)` cross-check is recommended only after user approval.
- Real calibration, distortion, exposure, reflection, synchronization, mechanical rigidity, and physical field-of-view constraints remain UNKNOWN/TODO.
- The pre-purchase core simulation program (regular/irregular waves, distance, and baseline cross-sections) is now complete as designed, including retained FAIL/BLOCKED evidence. A final local report is not created until the user confirms.
