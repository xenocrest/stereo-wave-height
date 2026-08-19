# HomeTank_001 Trial 1: uncalibrated coarse reconstruction

## Outcome

Final classification: `CALIBRATION_REQUIRED`.

The real-video input reached WASS `prepare` and `match` for all eight static pairs. `autocalibrate` formed a global essential matrix and triangulated 287 points before bundle adjustment, but its normal equations became non-positive-definite and the process terminated with return code `3221225477` (`0xC0000005`). Per the stop rule, `stereo` and the wave subset were not run. No xyzC or height result exists.

This is a preserved negative result. No WASS setting, focal hypothesis, historical configuration, or acceptance gate was changed after observing the failure.

## Frozen inputs

- Dataset: `HomeTank_001`, stored outside Git.
- cam0 / left: iQOO Z10 Turbo+.
- cam1 / right: iQOO Neo5S.
- Manual baseline: 650 mm = 0.650 m.
- Vertical camera height: approximately 1.700 m above static water.
- Common deployment pitch: approximately 40 degrees downward from horizontal.
- Derived optical-axis distance: approximately 2.645 m; derived only, not measured.
- Calibration: none.

The common 40-degree pitch is not a relative camera rotation. It was not inserted into `R_right_from_left`.

## Orientation normalization

Original MP4 files were not modified.

| Camera | Container rotation | Canonical transform | Result |
|---|---:|---|---|
| cam0 / left | -180 degrees | explicit 180-degree pixel rotation | 1920 x 1080 canonical frame |
| cam1 / right | 0 degrees | identity | 1920 x 1080 canonical frame |

WASS consumed only the extracted canonical frames. No cam0-specific branch was added to WASS.

## Synchronization

Pairing used original video PTS and the affine model `t_right = a * t_left + b`; equal frame numbers were never assumed. The accepted event sets and diagnostics are in [synchronization_summary.yaml](synchronization_summary.yaml).

Static fit:

- `a = 0.9981477463`;
- `b = 0.0744517600 s`;
- event-fit residual RMSE `0.007829704 s`;
- event-fit maximum absolute residual `0.014107640 s`.

Wave fit was completed for input readiness but not used for reconstruction:

- `a = 0.9998262151`;
- `b = 0.0710541191 s`;
- event-fit residual RMSE `0.005361428 s`;
- event-fit maximum absolute residual `0.011657261 s`.

The static reconstruction subset used a 0.010 s pairing tolerance. Its eight actual pair residual magnitudes were at most 0.007841 s.

## Coarse K/R/T hypothesis

No focal-length tag or phone calibration was available. Trial 1 therefore used one declared 70-degree horizontal-FOV hypothesis, not a parameter scan:

```text
K_L = K_R = [[1371.02208647243, 0, 960],
             [0, 1371.02208647243, 540],
             [0, 0, 1]]
D_L = D_R = [0, 0, 0, 0, 0]
```

Status: `ASSUMED_FOR_FEASIBILITY_ONLY`. The principal point is the image centre, and zero distortion is an uncalibrated approximation.

The frozen placement hypothesis was:

```text
R0 = identity(3)
T0 = [0.650, 0, 0]^T m
```

Status: `APPROXIMATE_UNCALIBRATED`. `R0` comes only from approximately parallel manual placement; `T0` contains only the measured baseline. The confirmed WASS CLI does not accept this pair as an autocalibration seed: WASS estimated its own normalized R/T, while 0.650 m would have supplied physical scale only if a valid xyzC had been produced.

At the derived 2.645 m distance, the declared hypothesis predicts approximately 336.958 px disparity and about 82.45% horizontal geometric overlap. The Trial-1 stereo-config copy therefore changed only `MIN_DISPARITY: 160 -> 64`, `MAX_DISPARITY: 320 -> 512`, and the provenance random seed. These changes were fixed before execution; stereo was never reached.

## Static subset

| ID | Left source index / PTS (s) | Right source index / PTS (s) | Pair residual (ms) |
|---|---|---|---:|
| 000000 | 1740 / 29.000744 | 1727 / 29.022989 | +1.510 |
| 000001 | 1800 / 30.000767 | 1787 / 30.022656 | +3.006 |
| 000002 | 1860 / 31.000789 | 1847 / 31.022322 | +4.503 |
| 000003 | 1920 / 32.000811 | 1907 / 32.021989 | +6.000 |
| 000004 | 1980 / 33.000844 | 1965 / 33.021600 | +7.430 |
| 000005 | 2040 / 34.000867 | 2024 / 34.004500 | -7.841 |
| 000006 | 2100 / 35.000889 | 2083 / 35.004289 | -6.221 |
| 000007 | 2160 / 36.000922 | 2143 / 36.003900 | -4.791 |

This interval is after the early exposure transitions and avoids the confirmed common luminance events.

## WASS stages

Runtime: native Windows WASS `1.11_heads/master-0-g6b82aeb`, MSVC/OpenCV 4.6.0. The runtime and WASS source were not modified.

| Stage | Status | Evidence |
|---|---|---|
| prepare | PASS | 8/8 workdirs created and intrinsic/distortion files read. |
| match | PASS_WITH_LIMITED_PLANAR_SUPPORT | 41–52 chirality-valid matches per frame; mean epipolar error 0.273–0.394 px. |
| autocalibrate | FAIL | 400 matches loaded, 288 global essential inliers, 287 points before SBA; non-positive-definite LAPACK/SBA system and process termination. |
| stereo | NOT RUN | Static gate stopped at failed autocalibration. |

The global pre-SBA result reported structure reprojection error `0.433354 +/- 0.278468 px` and epipolar error `0.866933 +/- 0.556987 px`. Its estimated rotation was far from the manual approximately-parallel hypothesis and its normalized translation was not baseline-axis dominated. Those values are diagnostic evidence of an untrustworthy coarse geometry, not accepted extrinsics.

## Geometry and failure classification

No `mesh_cam.xyzC` exists, so:

- raw point count: 0;
- XYZ range: unavailable;
- reconstructed distance: unavailable;
- static plane/water structure: not assessable;
- wave execution: prohibited by the failed static gate.

Synchronization is not classified as the primary blocker: all selected pairs met the declared tolerance and WASS matching produced repeatable non-zero correspondences. Surface observability remains a secondary risk because the scene is predominantly planar and the water is weakly textured. The immediate demonstrated blocker is that uncalibrated assumed K plus planar real imagery did not provide a numerically valid WASS autocalibration. A real calibration with non-coplanar calibration observations is required before another reconstruction attempt.

## Next action

Acquire a simple, traceable stereo calibration dataset for both phones in the unchanged rigid mount, determine K/distortion and relative R/T, then repeat the same small static gate. Do not run wave reconstruction or report height until static produces a physically plausible xyzC.
