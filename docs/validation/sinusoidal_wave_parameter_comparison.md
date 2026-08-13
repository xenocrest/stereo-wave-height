# Controlled sinusoidal-wave parameter comparison

Run date: 2026-08-13  
Status: **G0/G1/G2/G3 PASS**

## Purpose and boundary

This procurement-preparation experiment tests whether the frozen ideal-synthetic
pipeline remains stable when wave amplitude and temporal frequency change. It
is a `KINEMATIC_SYNTHETIC_WAVE_TEST`; water depth is still `UNKNOWN`, so the
chosen frequency/wavelength pairs are not claimed to satisfy a physical gravity-wave
dispersion relation. It does not establish real-camera or real-water accuracy.

## Controlled design

All groups use the candidate 2448 x 2048 camera geometry, 3.45 um pixel pitch,
nominal 8 mm ideal pinhole lens, zero distortion, baseline 0.20 m, scene distance
2.00 m, wavelength 0.80 m, phase 0, deterministic texture seed 20260811,
`ZGAP_PERCENTILE=99.5`, official WASS, official gridder 0.11.4 DCT, a 160 x 160
grid at 0.01 m, and unchanged acceptance gates. These are simulation parameters,
not confirmed hardware values.

Each separately generated group contains two independent static frames followed
by ten dynamic frames. Only the static frames form `Z0`. At 5 Hz, 0.5 Hz has
10 samples/period and 1 Hz has 5 samples/period; both ten-frame sequences cover
an integer number of periods. The 1 Hz groups have much less temporal sampling
margin. Spatially, every group has 80 samples/wavelength and a 1.60 m periodic
sample length (two wavelengths).

| Group | Changed factor | A (m) | f (Hz) | samples/period |
|---|---|---:|---:|---:|
| G0 | baseline | 0.010 | 0.50 | 10 |
| G1 | amplitude only | 0.030 | 0.50 | 10 |
| G2 | frequency only | 0.010 | 1.00 | 5 |
| G3 | combined stress | 0.030 | 1.00 | 5 |

## End-to-end execution and support

Every group independently ran truth -> stereo PNG -> prepare -> match ->
autocalibrate -> stereo -> xyzC -> shared-plane official grid -> explicit
`x_world=x_grid+0.10 m` alignment -> independent `Z0` -> `H` -> validation.
All external stages returned zero. No truth disparity or truth point cloud was
given to WASS.

| Group | triangulated range | largest-component range | minimum retention | raw support | finite grid | holes |
|---|---:|---:|---:|---:|---:|---:|
| G0 | 4,322,503--4,337,716 | 4,320,224--4,336,691 | 99.9409% | 100% | 100% | 0% |
| G1 | 4,324,706--4,358,632 | 4,323,792--4,358,006 | 99.8449% | 100% | 100% | 0% |
| G2 | 4,322,503--4,335,514 | 4,322,122--4,334,186 | 99.9625% | 100% | 100% | 0% |
| G3 | 4,320,548--4,354,517 | 4,319,465--4,351,618 | 99.8593% | 100% | 100% | 0% |

No group triggered the pre-registered 95% support stop rule.

## Height-field results

Metrics use the pre-registered raw-observation validation-eligible domain. All
values below are millimetres except coverage.

| Group | bias | RMSE | MAE | max | P90 | P95 | P99 | result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| G0 | -0.258 | 0.859 | 0.691 | 2.509 | 1.396 | 1.642 | 2.120 | PASS |
| G1 | -0.433 | 1.030 | 0.849 | 3.398 | 1.679 | 1.949 | 2.422 | PASS |
| G2 | -0.109 | 0.739 | 0.604 | 2.099 | 1.221 | 1.381 | 1.735 | PASS |
| G3 | -0.545 | 1.131 | 0.925 | 3.672 | 1.876 | 2.166 | 2.611 | PASS |

Frozen gates are RMSE <=10 mm, MAE <=10 mm, maximum absolute error <=30 mm,
raw support >=95%, and hole rate <=5%. All groups pass without post-hoc changes.

## Wave-parameter recovery

The verified estimator uses the center physical row and world-aligned x.
Amplitude/wavelength/frequency thresholds were not pre-registered, so these are
report-only auxiliary indicators.

| Group | A calc (mm) | A error (mm / %) | lambda calc/error (m) | f calc/error (Hz) | wrapped phase error (rad) |
|---|---:|---:|---:|---:|---:|
| G0 | 9.694 | -0.306 / -3.058% | 0.800 / <1e-12 | 0.50 / 0 | +0.000207 |
| G1 | 29.596 | -0.404 / -1.346% | 0.800 / <1e-12 | 0.50 / 0 | +0.000406 |
| G2 | 9.689 | -0.311 / -3.113% | 0.800 / <1e-12 | 1.00 / 0 | -0.002633 |
| G3 | 29.659 | -0.341 / -1.135% | 0.800 / <1e-12 | 1.00 / 0 | -0.003247 |

## Controlled comparisons

G0 -> G1 changes amplitude only. RMSE rises 0.171 mm, MAE 0.157 mm, maximum
error 0.889 mm, while raw support remains 100% and minimum component retention
drops only 0.096 percentage points. Relative amplitude underestimation improves
from 3.058% to 1.346%. The larger amplitude causes a small absolute-error
increase, not a support failure.

G0 -> G2 changes frequency only. Despite sampling falling from 10 to 5 points
per period, RMSE falls 0.120 mm and MAE falls 0.088 mm; frequency and wavelength
remain exactly at their discrete truth bins. There is no evidence of a temporal
sampling failure in this 1 Hz ideal synchronized test, but five samples/period
has limited margin and does not justify higher-frequency extrapolation.

G3 combines both tested changes. It has the largest RMSE (1.131 mm), MAE
(0.925 mm), and maximum error (3.672 mm), but retains 100% raw support and stays
far inside all gates. Because G1 and G2 pass and G3 also passes, no new harmful
amplitude-frequency interaction is observed within this matrix.

## Conclusion and limits

The frozen software chain is stable across A=10--30 mm and f=0.5--1.0 Hz for
this one ideal pinhole geometry and kinematic sinusoid. This is sufficient to
close the planned controlled regular-wave matrix. It is not proof for arbitrary
or irregular waves, real gravity-wave physics, optical reflection/refraction,
noise, distortion, synchronization error, calibration uncertainty, or real
1 cm performance. An irregular-wave test may be designed next only as a new,
pre-registered synthetic validation; procurement and physical validation still
require real hardware, calibration, synchronization, and independent water-height
references.

Traceable compact results are in
[`prepurchase_wave_matrix_metrics.json`](prepurchase_wave_matrix_metrics.json).
Large PNG, xyzC and NetCDF products remain outside Git under
`D:/stereo-wave-height-runs/prepurchase-wave-matrix-20260813`.
