# Controlled scene-distance validation

## Scope and frozen design

This pre-purchase test changes only the virtual camera-to-static-water distance. It is an ideal pinhole simulation, not a real-camera or real-water result. The camera candidate (2448 x 2048, 3.45 um pixels, nominal 8 mm lens), focal length 2318.840580 px, baseline 0.20 m, deterministic texture and timestamps, wave (`A=0.030 m`, `lambda=0.80 m`, `f=0.50 Hz`, zero initial phase), WASS settings including `ZGAP_PERCENTILE=99.5`, official DCT grid (160 x 160 at 0.01 m), explicit `x_world=x_grid+0.10 m`, and gates were frozen. Each distance has two independent static frames for `Z0` and ten dynamic frames. Distances are `SIMULATION_TEST_PARAMETER`, not selected hardware deployment values.

The gates remain RMSE and MAE <=0.010 m, maximum absolute error <=0.030 m, minimum raw-observation support >=95%, and hole rate <=5%. A finite DCT value is not treated as raw observation support.

## Distance selection from geometry

For rectified pinhole stereo, `d=f_px B/Z` and the local one-pixel depth sensitivity is `|dZ/dd|=Z^2/(f_px B)`. The horizontal common field width used here is `(image_width_px-d) Z/f_px`; the conservative value below uses the nearest wave depth `Z-A`. The frozen disparity bounds are 160--320 px and the required physical width is 1.59 m.

| candidate Z | nominal d | wave d range | sensitivity | minimum common width | decision |
|---:|---:|---:|---:|---:|---|
| 1.50 m | 309.179 px | 303.116--315.489 px | 4.852 mm/px | 1.352 m | reject: insufficient common width |
| 1.75 m (D1) | 265.010 px | 260.544--269.633 px | 6.604 mm/px | 1.616 m | selected near case |
| 2.00 m (D0) | 231.884 px | 228.457--235.415 px | 8.625 mm/px | 1.880 m | frozen reference |
| 2.50 m (D2) | 185.507 px | 183.308--187.760 px | 13.477 mm/px | 2.408 m | selected far case |
| 3.00 m | 154.589 px | 153.059--156.151 px | 19.406 mm/px | 2.935 m | reject: below minimum disparity |

D1 and D2 are the nearest/farthest explanatory cases inside both constraints. No final deployment distance is inferred.

## Execution and provenance

D1 and D2 use newly rendered, distance-specific images; images were not regenerated between WASS stages. Prepare and match succeeded on all 12 frames, and autocalibration succeeded using the pre-registered all-dynamic subset `000002..000011`; its official exterior calibration was distributed to the two static workdirs. D1 completed stereo and `wassgridsurface 0.11.4`. D0 reuses the G1 evidence because every frozen factor and its 2.00 m distance are identical. Run products remain outside Git under `D:\stereo-wave-height-runs\scene-distance-20260814`.

Manifest and configuration hashes are preserved in `scene_distance_validation_metrics.json`. WASS and wassgridsurface source were not modified.

## Results

| item | D1 1.75 m | D0 2.00 m | D2 2.50 m |
|---|---:|---:|---:|
| prepare / match / autocalibrate | 12/12 / 12/12 / PASS | reused G1 PASS | 12/12 / 12/12 / PASS |
| triangulated points min/mean/max | 4,410,713 / 4,429,758 / 4,445,654 | 4,324,706 / 4,347,761 / 4,358,632 | 1,467,806 on frame 0 |
| largest component min/mean/max | 3,240,396 / 4,305,227 / 4,437,630 | 4,323,792 / 4,344,854 / 4,358,006 | 610,135 on frame 0 |
| retention min/mean/max | 72.939% / 97.194% / 99.907% | 99.845% / 99.933% / 99.986% | 41.568% on frame 0 |
| raw support min/mean/max | 71.758% / 94.875% / 97.074% | 100% / 100% / 100% | N/A |
| bias | -0.258 mm | -0.433 mm | N/A |
| RMSE / MAE | 2.832 / 1.789 mm | 1.030 / 0.849 mm | N/A |
| maximum error | 23.509 mm | 3.398 mm | N/A |
| DCT hole rate | 0% | 0% | N/A |
| recovered A error | -0.424 mm | -0.404 mm | N/A |
| recovered lambda / f | 0.800 m / 0.500 Hz | 0.800 m / 0.500 Hz | N/A |
| phase error | +0.02637 rad | +0.00041 rad | N/A |
| result | **FAIL raw-support gate** | **PASS** | **BLOCKED at stereo plane fit** |

D1's failure is not a height-error failure: frame `000003` alone drops to 72.939% component retention and 71.758% raw grid support, making the required minimum support fail. The DCT output remains finite everywhere, demonstrating why finite-grid coverage cannot replace observation support. D0 passes.

D2 fails fast on static frame `000000`: WASS triangulates 1,467,806 points, retains 610,135 in the largest component, finds zero RANSAC plane inliers, emits plane coefficients `0 0 0 0`, and terminates. No grid or height metrics are reported. This is `BLOCKED_AT_STEREO_PLANE_FIT`; no parameter was tuned after observing it.

## Fixed physical-point tracking

Nearest official nodes were frozen once for P1 `(0.005,-0.005)`, P2 `(-0.595,-0.005)`, P3 `(0.605,-0.005)`, P4 `(0.405,0.395)`, and P5 `(-0.795,0.695)` m in world coordinates. D0 point RMSE spans 0.602--1.756 mm. D1 spans 1.182--7.921 mm; the largest is P5 near the domain edge. D2 has no valid reconstructed series. The partial trend cannot establish a monotonic distance law.

## Interpretation and next decision

The theoretical trend is confirmed only at the geometry level: disparity falls and one-pixel depth sensitivity worsens as distance grows. The end-to-end results are not monotonic evidence because D1 has a single-frame support collapse and D2 stops before gridding. The supported operating interval is not established beyond the passing 2.00 m reference. These are procurement constraints, not proof that 2.00 m is optimal.

Baseline validation may proceed only as a separate one-factor study at the passing frozen D0=2.00 m reference. It must not claim that the unresolved D1/D2 limitations are closed. No final comprehensive procurement report is produced here.

## UNKNOWN / TODO

- The exact cause of D1 frame `000003` component fragmentation is UNKNOWN.
- The exact cause of D2's low triangulated count, component loss, and zero-plane RANSAC result is UNKNOWN; attribution to distance sensitivity alone would be unsupported.
- Real lens distortion, real calibration, optical texture, exposure, timing, water reflection, and final physical baseline/distance remain TODO.
- The acceptable physical deployment-distance interval remains TODO.
