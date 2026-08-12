# Case 1 end-to-end repeatability

Run date: 2026-08-12

Status: **NUMERICALLY DETERMINISTIC (B); ZGAP 99.5 FROZEN; CASE 1 COMPLETE**

## 1. Frozen condition

This experiment stopped parameter adaptation and used `ZGAP_PERCENTILE=99.5`.
The four frozen images, frame order, calibration, matcher/autocalibration
products, baseline 0.20 m, working distance 2.00 m, stereo/matcher configs,
160 x 160 grid, grid extent, DCT settings, `--parallel 1`, static-only temporal
mean `Z0`, `H=Z-Z0`, and validation implementation were unchanged. Baseline and
distance remain simulation test parameters.

Selected SHA-256 provenance:

| artifact | SHA-256 |
|---|---|
| manifest.json | `C21D17A97143576A1015579E48BD4B92F2370468DBADC19F073F0C8CB82EF990` |
| camera.yaml | `373F36008DE88EC341B68D660B60B6390E54BFDB182E834DDBE6CAEBE8A630A1` |
| intrinsics 00/01 | `210E2BA3B6FF1FBD544479B2CB942F4FFD6073C7BB103273B667321CD900012F` |
| distortion 00/01 | `639AA79C9B9507EFCFE636AC60F26326969C85C01F5EBE1BED40A151C3A3EA84` |
| matcher_config.txt | `BAE1E60A3680BC0193628C35BFFB7FD68BA5E8C672F12A489284BD25B25EAF32` |
| stereo_config.txt | `998E5C10065D49B2F4546A96D25962DEC5FA458F44C5190EBD95C13271C2B192` |
| gridconfig.txt | `701069A2761277A71F7F198B2FBE9562C106D6D58B2869C96A3D96BB8E2A23DE` |
| shared planes.txt | `E3CE47C09F4A0286BA32E67AAAC503C5210251216608C5E56503451E505D46E3` |

All large artifacts remain outside Git at
`D:/stereo-wave-height-runs/case1-repeatability-20260812`.

## 2. Layer A: WASS stereo

Official `wass_stereo` was run three times for all four frames. Every return
code was zero. All repeated outputs were bitwise identical per frame:

| frames | final points | xyzC SHA-256 | plane d | scale |
|---|---:|---|---:|---:|
| static 000000/1 | 4,321,866 | `B0D528C791ECFA9793A3E2B0E61416A3C5AD766DF80722F8E3E8F4454704F754` | -9.996914151789463 | 0.29983660130718953 |
| raised 000002/3 | 4,326,851 | `EB449F689E9C5ABC92E680497A0B7039EEA042EB03183BA221241AD55D62539D` | -9.950726196404917 | 0.29983660130718953 |

All four plane coefficients and scales had zero observed run-to-run variation.
Recovered plane position therefore also had zero variation. Layer A is
**bitwise deterministic** under the frozen condition.

## 3. Layer B: official DCT gridder

One fixed Layer-A work tree and planes file were gridded five times with
`wassgridsurface 0.11.4`, DCT and `--parallel 1`. All NetCDF SHA-256 values and
all `config.mat` hashes differed. This alone is not treated as numerical
failure. `X_grid`, `Y_grid`, scale (0.20 m), finite mask (102,400/102,400 Z
cells), and frame order were identical.

Across all ten pairs of the five Z arrays:

- maximum observed `max |delta Z|`: **0.020553 mm**;
- maximum pairwise `mean |delta Z|`: **0.003222 mm**;
- maximum pairwise `RMSE(delta Z)`: **0.004372 mm**;
- 102,387--102,396 of 102,400 float cells differed in typical pairs.

Thus Layer B is not bitwise deterministic, but its variation is more than two
orders of magnitude below the approximately 1 mm Case 1 error scale.

## 4. Layer C: height pipeline

Each NetCDF used the same first two static frames for `valid_temporal_mean`,
then the same `H=Z-Z0` and full eligible domain.

| metric | minimum | maximum | span |
|---|---:|---:|---:|
| mean H | 9.105802 mm | 9.107632 mm | 0.001830 mm |
| signed bias | -0.894198 mm | -0.892368 mm | 0.001830 mm |
| RMSE | 1.026197 mm | 1.027406 mm | 0.001209 mm |
| MAE | 0.914968 mm | 0.916601 mm | 0.001633 mm |
| maximum error | 1.641137 mm | 1.646604 mm | 0.005466 mm |
| coverage | 100% | 100% | 0 |
| hole rate | 0% | 0% | 0 |

No run changes the Case 1 acceptance conclusion.

## 5. Strict single-thread diagnostic and cause

One additional run set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and
`MKL_NUM_THREADS=1`, while retaining gridder `--parallel 1`. Relative to normal
run 1, `max |delta Z|` was 0.018790 mm and `RMSE(delta Z)` was 0.004729 mm;
height RMSE was 1.027118 mm. Strict thread limits therefore do not remove or
materially change the variation.

Installed 0.11.4 source provides the direct cause: `DCTInterpolator.py`
initializes every solve with unseeded `torch.rand`; `wassgridsurface.py` also
uses unseeded NumPy permutations/shuffles during point quantization. No seed is
exposed by the invoked CLI. `--parallel 1` means one grid task/interpolator,
not deterministic random initialization and not a guarantee about all math
library worker threads. The solver uses float32 PyTorch Rprop and stops by the
fixed iteration/tolerance logic. No algorithm was modified.

## 6. Historical ZGAP=99 discrepancy

Historical and sweep-iteration r=99 xyzC hashes are identical for every frame;
gridconfig is identical, and `planes.txt` numerical text is identical (its file
hash difference is line-ending serialization only). Frame combination, scale,
reference definition and grid geometry are unchanged. The discrepancy is
therefore not WASS stereo, configuration geometry, Z0 membership or frame
ordering. It is attributable to the confirmed unseeded DCT/point-quantization
path acting on the sparse 51.45% raw-support domain. Sparse unsupported regions
amplify different stochastic DCT solutions, explaining why that old full-grid
RMSE difference was much larger than the fully supported r=99.5 repeatability
spread. The old number was not recreated or altered.

## 7. Classification and gate

The frozen chain is classified **B: numerically deterministic**:

- WASS stereo is bitwise deterministic;
- grid-file hashes are not stable, but physical Z variation is bounded to
  0.0206 mm maximum and height-metric spans are at most 0.0055 mm;
- this cannot affect millimetre/centimetre Case 1 conclusions.

`ZGAP_PERCENTILE=99.5` may now be formally frozen for this synthetic Case 1
geometry. Case 1 can conclude as a successful ideal-simulation validation.
Case 2 may be authorized as the next separate task, but was not started here.
This does not establish real-camera or real-water accuracy, and the existing
cluster `OBSERVABILITY_LIMITATION` remains documented.

Project-status note: Case 2 was subsequently completed in a separate run; this
sentence is retained as the boundary of the repeatability task. See
[`case2_sinusoidal_wave.md`](case2_sinusoidal_wave.md) for the later result.
