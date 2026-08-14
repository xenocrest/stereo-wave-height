# IRR-1 确定性多分量不规则波验证

Run date: 2026-08-13  
Status: **ORIGINAL IRR-1 FAIL PRESERVED; IRR-1A PASS**

## 目的与冻结真值

IRR-1 asks whether the complete chain that passed single sinusoids also recovers
a continuous deterministic multi-component surface. Formal validation remains
the direct field error `H_calc-H_true`; no sinusoid estimator participates.

The pre-run frozen truth is

$$
H_{true}(x,t)=\sum_{i=1}^{3} A_i\sin(k_i x-\omega_i t+\phi_i),
\qquad k_i=\frac{2\pi}{\lambda_i},\qquad \omega_i=2\pi f_i.
$$

| component | A (m) | lambda (m) | f (Hz) | phase (rad) |
|---|---:|---:|---:|---:|
| 1 | 0.015 | 0.80 | 0.50 | 0 |
| 2 | 0.008 | 0.50 | 0.80 | pi/3 |
| 3 | 0.005 | 1.20 | 0.30 | -pi/4 |

This is a `KINEMATIC_SYNTHETIC_WAVE_TEST`. Water depth is `UNKNOWN`; the
components are not asserted to satisfy a gravity-wave dispersion relation.

## 运行前合规性与采样

The exact triangle-inequality height bound is +/-0.028 m. A dense deterministic
evaluation over x `[-0.9,0.9] m` and the 10 s repeat gives -0.0279815 to
+0.0206351 m (48.6166 mm peak-to-peak). The evaluated maximum absolute slope is
0.232950 and its analytical upper bound is 0.244521. Maximum evaluated temporal
rate is 0.0921561 m/s; its analytical upper bound is 0.0967611 m/s. These checks
were completed before image generation and the candidate parameters were frozen
without adjustment.

At grid spacing 0.01 m, the components have 80, 50 and 120 samples/wavelength.
At 5 Hz they have 10, 6.25 and 16.67 samples/period. All frequencies are integer
multiples of 0.1 Hz, so the exact common repeat period is 10 s. Fifty dynamic
samples at t=0.0--9.8 s represent one complete discrete repeat window and cover
5, 8 and 3 component cycles. Two preceding independent static frames are the
only intended `Z0` input.

## 冻结观测、位置与时间

Camera, texture, baseline 0.20 m, distance 2.00 m, ZGAP 99.5, grid, DCT and
acceptance gates match the completed regular-wave matrix. The explicit mapping
remains `x_world=x_grid+0.10 m`. Nearest-grid-node sampling was frozen before
reconstruction for P1 `(0.005,-0.005)`, P2 `(-0.595,-0.005)`, P3
`(0.605,-0.005)`, P4 `(-0.195,0.395)`, P5 `(0.405,-0.405)` and P6
`(-0.795,0.695)` metres in world coordinates. Key dynamic times were frozen at
0.0, 3.4 and 6.8 s.

## WASS 执行与阻塞失败

All 52 stereo pairs were generated and copied into the WASS workspace without
truth exposure. `prepare` and `match` returned zero for all 52 frames.
`autocalibrate` loaded 95,083 matches, accepted 95,076 positive-depth points,
reported structure reprojection error near `2.56e-6 px`, and SBA converged in
one iteration. It then estimated a homography with determinant 0.999967 and
terminated with `SBA failed`, returning unsigned Windows code 4294967295.

One controlled retry used the identical workdirs and unchanged executable and
configuration. It reproduced the same numerical output and failure. Therefore
this is not treated as a transient random event. No WASS parameter, formula,
frame set or acceptance gate was changed after observing the result.

Per the fail-fast protocol, `stereo` and `wassgridsurface` were not run. Hence
triangulated counts, component retention, raw support, `H_calc`, global errors,
representative-point errors, key-time comparisons and frequency diagnostics are
**NOT AVAILABLE**. Inventing those values or reusing earlier output would violate
the end-to-end requirement.

## 原始结论

IRR-1 is **not passed** and is classified `BLOCKED_AT_AUTOCALIBRATION`. The
failure is a newly observed pipeline scaling/conditioning issue for this frozen
52-frame joint autocalibration set. The evidence localizes it after successful
matching and SBA, at the post-SBA homography acceptance path; the exact internal
rejection condition remains `UNKNOWN/TODO` pending source-backed diagnosis.

This result does not show that WASS stereo or gridder fails on the irregular
surface, because those stages were never reached. It also does not justify
changing ZGAP, DCT, grid or height gates. Scene-distance validation must **not**
begin until IRR-1 is resolved by a separately pre-registered diagnosis (for
example, confirming the official autocalibration frame-selection constraints)
without redefining this failed run.

Compact evidence is in
[`data/irregular_wave_metrics.json`](data/irregular_wave_metrics.json). Large
images and work products remain outside Git at
`D:/stereo-wave-height-runs/irregular-wave-20260813`.

## IRR-1A 适配结果

A subsequent pre-registered diagnosis established that failure is not monotonic
with frame count and that the source requires strict post-SBA error improvement.
The frozen AC-10D subset `[2,7,13,18,24,29,35,40,46,51]` spans the full dynamic
window. Its unchanged calibration successfully drove all 52 stereo frames and
the official shared grid. See
[`irregular_wave_autocalibration_diagnosis.md`](irregular_wave_autocalibration_diagnosis.md).

On the original frozen truth, representative points, times and eligible-domain
rules, IRR-1A obtains bias 0.0364 mm, RMSE 2.3676 mm, MAE 1.8822 mm, maximum
error 8.7321 mm, P90/P95/P99 3.9126/4.6720/6.1705 mm. Dynamic raw support is
99.9961--100%, component retention 99.7497--99.9805%, finite coverage 100%, and
hole rate 0.0000781%. All frozen gates pass.

Point RMSE ranges 1.5068--3.3839 mm; point MAE 1.1720--2.9033 mm; point maximum
error 4.1826--7.5763 mm. The pre-registered 0.0/3.4/6.8 s comparisons are stored
with all 300 point-time rows in
[`data/irregular_wave_points.csv`](data/irregular_wave_points.csv). P1/P2 have
positive biases 2.874/2.700 mm while other points range -0.789 to -0.202 mm,
showing a localized spatial bias pattern that remains below formal gates and
should be tracked in deployment validation.

IRR-1A passes. Scene-distance validation may proceed as a new pre-registered
task, while preserving the original IRR-1 failure and the localized-bias note.
