# HomeTank_004 On-demand Synchronization Tolerance Validation

## Method and boundaries

The left PTS is fixed. For each dataset, $R_0$ is the nearest right decoded PTS to $a t_L+b$; only the right frame changes from $R_{-3}$ through $R_{+3}$. Actual residual and normalized residual are

$$
\Delta t_k=t_{R,k}-(a t_L+b),\qquad \rho_k=|\Delta t_k|/T_{frame}.
$$

All 14 calls used unchanged OpenCV K/D/R/T, rectification policy, WASS configuration, valid-point RANSAC and height mathematics. Ruler data was not read. $R_0$ is a model-predicted candidate, not physical truth. Formal selection remains $R_0$ and never selects the best reconstruction retrospectively.

## Static results

| k | Right PTS time (s) | Δt (ms) | ρ | WASS | Retained matches | XYZ | Plane RMS (mm) | Normal Δ (deg) | H median/RMS (mm) |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| -3 | 9.950267 | -41.803 | 2.508 | PASS | 34 | 165437 | 6.688 | 56.061 | -1.154 / 6.688 |
| -2 | 9.966933 | -25.137 | 1.508 | PASS | 42 | 166494 | 6.789 | 56.621 | -1.202 / 6.789 |
| -1 | 9.983600 | -8.470 | 0.508 | PASS | 41 | 166523 | 1.718 | 0.265 | -0.354 / 1.718 |
| 0 | 10.000267 | +8.197 | 0.492 | PASS | 41 | 167422 | 2.509 | 0.000 | -0.430 / 2.509 |
| +1 | 10.016933 | +24.863 | 1.492 | PASS | 46 | 161381 | 1.844 | 0.201 | -0.386 / 1.844 |
| +2 | 10.033600 | +41.530 | 2.492 | PASS | 43 | 165385 | 4.510 | 3.219 | -0.631 / 4.510 |
| +3 | 10.050267 | +58.197 | 3.492 | PASS | 35 | 167485 | 1.996 | 1.267 | -0.337 / 1.996 |

## Wave results

| k | Right PTS time (s) | Δt (ms) | ρ | WASS | Retained matches | XYZ | Plane RMS (mm) | Normal Δ (deg) | H median/RMS (mm) |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| -3 | 19.883867 | -52.606 | 3.156 | PASS | 29 | 74785 | 6.828 | 83.436 | -588.562 / 588.995 |
| -2 | 19.900533 | -35.940 | 2.156 | PASS | 33 | 75696 | 1.619 | 7.301 | 40.743 / 40.833 |
| -1 | 19.917200 | -19.272 | 1.156 | PASS | 28 | 87122 | 1.850 | 4.420 | 24.954 / 25.113 |
| 0 | 19.933867 | -2.606 | 0.156 | PASS | 34 | 86911 | 1.500 | 0.000 | -5.865 / 5.887 |
| +1 | 19.950533 | +14.060 | 0.844 | PASS | 34 | 91889 | 3.321 | 1.576 | 3.370 / 5.108 |
| +2 | 19.967200 | +30.727 | 1.844 | PASS | 33 | 123457 | 4.824 | 70.970 | -393.357 / 393.606 |
| +3 | 19.983867 | +47.394 | 2.844 | PASS | 41 | 130966 | 6.420 | 4.524 | 20.262 / 21.319 |

All executable stages returned PASS. This alone is insufficient: large plane-normal and height failures appear at $|k|\ge2$. Match count is not a reliable quality proxy either; the wave $k=+2$ failure retained 33 matches and more XYZ than $R_0$.

## Engineering gate

The controlled evidence supports a conservative policy:

- `ACCEPTED`: $k=0$ only;
- `WARNING`: $|k|=1$;
- `REJECTED`: $|k|\ge2$.

This is an on-demand engineering tolerance relative to the predicted $R_0$, not proof of strict frame synchronization and not a universal physical-accuracy claim. Static and wave each use one target time; broader deployment validation remains required.

The formal static and wave samples therefore use $R_0$, not the best-looking candidate. Both completed through the video-mode backend with `SINGLE_FRAME_PIPELINE_PASS_WITH_SYNC_WARNING` and `PHYSICAL_ACCURACY_NOT_ESTABLISHED`.
