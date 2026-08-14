# Baseline-distance cross-check

## Purpose

XZ-1 is the single authorized supplemental deployment point: baseline 0.25 m and scene distance 2.50 m. It tests whether increasing baseline can remove the former D2 reconstruction blocker while recovering a disparity geometry similar to the passing reference. It is not a two-dimensional parameter scan.

The old D2 point `(B=0.20 m,Z=2.50 m)` stopped on its first static frame after 1,467,806 triangulated points, a 610,135-point largest component (41.568%), and zero plane-RANSAC inliers. No grid or height result existed.

## Theory

The governing quantities are

$$
d=\frac{f_{px}B}{Z}, \qquad S_Z=\frac{Z^2}{f_{px}B}, \qquad
\theta=2\arctan\left(\frac{B}{2Z}\right).
$$

| quantity | REF 0.20/2.00 | D2-old 0.20/2.50 | XZ-1 0.25/2.50 |
|---|---:|---:|---:|
| B/Z | 0.100 | 0.080 | 0.100 |
| nominal disparity | 231.884 px | 185.507 px | 231.884 px |
| +/-30 mm disparity | 228.457--235.415 px | 183.308--187.760 px | 229.134--234.700 px |
| depth sensitivity | 8.625 mm/px | 13.477 mm/px | 10.781 mm/px |
| conservative common FOV | 1.880 m | 2.408 m | 2.358 m |
| central ray angle | 5.725 deg | 4.581 deg | 5.725 deg |

REF and XZ-1 share B/Z, nominal disparity, and central ray angle. They do not share absolute depth sensitivity, footprint, common FOV, viewing rays, or matching distribution. Similar disparity is therefore a controlled hypothesis, not a similarity proof.

## Frozen configuration

Only baseline and scene distance differ from the deployment validation reference. Camera resolution/pitch/nominal lens, ideal zero distortion, deterministic texture and timestamps, wave (`A=0.030 m`, `lambda=0.80 m`, `f=0.50 Hz`, `phi=0`), two static plus ten dynamic frames, matcher/stereo configs, `ZGAP_PERCENTILE=99.5`, official DCT grid, and acceptance gates remain frozen. `Z0` uses only frames 000000--000001. Coordinate alignment is explicitly `x_world=x_grid+0.125 m`.

Autocalibration used exactly dynamic frames `000002..000011`. Per-frame matcher counts were 678, 678, 617, 584, 550, 563, 604, 629, 628, 625, 617, and 648; min/mean/max were 550/618.417/678. Calibration and config hashes are in the metrics JSON.

## WASS and blocker result

| stage | result |
|---|---|
| prepare | 12/12 PASS |
| match | 12/12 PASS |
| autocalibrate | PASS, frozen dynamic subset |
| stereo | 12/12 PASS |
| official wassgridsurface | PASS |

| reconstruction metric | D2-old first frame | XZ-1 min/mean/max |
|---|---:|---:|
| triangulated points | 1,467,806 | 3,870,685 / 3,883,116 / 3,913,468 |
| largest component | 610,135 | 3,804,553 / 3,829,344 / 3,891,986 |
| retention | 41.568% | 98.106% / 98.614% / 99.451% |
| plane RANSAC inliers | 0 | 3,804,553 / 3,829,344 / 3,891,986 |
| plane fit | FAIL | 12/12 PASS |

The original D2 connected-component/plane-fit blocker is removed. This conclusion is directly supported by the same frozen WASS executable and configuration, not by parameter tuning.

## Support and height acceptance

| metric | XZ-1 |
|---|---:|
| raw support min/mean/max | 99.988% / 99.998% / 100% |
| finite grid coverage | 100% |
| hole rate | 0% |
| signed bias | -0.713 mm |
| RMSE | 1.551 mm |
| MAE | 1.222 mm |
| maximum absolute error | 8.306 mm |
| P50 / P90 | 1.063 / 2.288 mm |
| P95 / P99 | 2.771 / 4.775 mm |

XZ-1 passes every frozen gate: RMSE and MAE <=10 mm, maximum <=30 mm, raw support >=95%, and hole rate <=5%.

Recovered wave parameters are amplitude 30.259 mm (error +0.259 mm), wavelength 0.800 m (error below numerical precision), frequency 0.500 Hz (zero discrete error), and phase error +0.003166 rad.

## Classification and meaning

XZ-1 is **PASS**, classification A. Increasing baseline from 0.20 to 0.25 m at the frozen 2.50 m scene distance removed the former reconstruction blocker and also passed height acceptance. This is direct evidence of baseline-distance coupling in this controlled ideal simulation.

It does not prove that 2.50 m is a universally valid distance, 0.25 m is an optimal baseline, equal B/Z always succeeds, or the complete deployment region $(B,Z)\in\Omega_{valid}$ is known. Real calibration, lens distortion, optical water texture/reflection, synchronization, mechanical rigidity, and physical deployment remain UNKNOWN/TODO.

The planned pre-purchase simulation evidence is now complete. The final local user report remains intentionally uncreated until explicit confirmation.
