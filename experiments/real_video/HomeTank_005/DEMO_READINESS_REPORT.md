# HomeTank_005 Full-pixel Demo Readiness Report

## Scope and integrity boundary

This is a presentation demo, not a validated measurement. The formal conclusion remains `CALIBRATION_GEOMETRY_UNRELIABLE`; package `HomeTank_005_demo_only_v1` is permanently marked `PRESENTATION_DEMO_ONLY` and `GEOMETRY_UNVERIFIED_NOT_FOR_VALIDATED_MEASUREMENT`. It cannot pass the production promotion gate.

The demo may state that software generates a finite pixel-wise relative surface-shape field from real stereo video with explicit provenance. It must not state that every pixel is directly measured, that HomeTank_005 has millimetre accuracy, or that the full-pixel field passed independent physical validation.

## Frozen geometry and ROI

| Item | Value |
|---|---:|
| Demo calibration | `HomeTank_005_demo_only_v1` |
| Selected model / baseline | `OPENCV_5_COEFFICIENT` / 0.093345242 m |
| Artifact roundtrip | PASS |
| Common-FOV ID | `fov_01ec3cc9db2ec11f` |
| Common-FOV bbox / ratio | `[0, 275, 520, 720]` / 9.7858% |
| Water ROI (exclusive xyxy) | `[20, 350, 480, 680]` |
| ROI pixels | 151,800 |

## Real WASS runs

Reference request 9.000 s extracted LEFT 9.008200 s and RIGHT 9.000233 s (pair residual -5.567 ms), with no fallback. WASS produced 99,954 XYZ points in 12.148 s. A real-XYZ plane was identifiable, but RMS 40.502 mm failed the formal 10 mm gate. The retained demo-only reference has LOW confidence and preserves this failure.

Measurement request 48.000 s extracted LEFT 47.999522 s and RIGHT 48.001267 s (pair residual 4.145 ms), with no fallback. WASS prepare/match/stereo passed, producing 98,438 XYZ points in 12.291 s. Current-frame water support contains 65,280 points and plane RMS is 11.837 mm. No matcher/photometric A/B was run.

The two WASS run products were not in an invariant cross-frame point-cloud frame; direct reference subtraction produced an obviously non-physical approximately -0.51 m offset. The demo does **not** publish it as height. It visualizes signed orthogonal surface-shape residual relative to the measurement frame robust WASS base plane, with this fallback recorded in metadata.

## Constrained full-domain model

The model uses 65,280 real WASS water points. Physical surface coordinates are normalized for the demo grid because canonical pixel-to-WASS correspondence is unverified. This is `UNVERIFIED_NORMALIZED_PHYSICAL_DOMAIN_FOR_DEMO_ONLY`; no ruler or manual truth enters reconstruction.

It uses `BASE_QUADRATIC + REGULARIZED_GRID_SURFACE` on 64 x 96 cells: weighted data fidelity, Laplacian and bi-Laplacian penalties, plus residual-to-zero ridge, followed by bilinear upsampling. The robust guard is P01/P99 plus the larger of three MAD scales or 25% robust span.

| Metric | Result |
|---|---:|
| Finite ROI height | 151,800 / 151,800 (100.000%) |
| OBSERVED / ESTIMATED_LOCAL | 0 / 0 |
| ESTIMATED_GLOBAL_MODEL | 151,800 (100.000%) |
| LOW / MEDIUM / HIGH confidence | 97,521 / 54,279 / 0 |
| Height min / max | -9.686 / +18.705 mm |
| Height median / mean | +0.816 / +0.837 mm |
| Range-guard clipped pixels | 0 |

`OBSERVED=0` is deliberate: real XYZ exists, but canonical-pixel correspondence is not trustworthy. Calling normalized-domain samples direct image observations would be false provenance. Classification is `MODEL_ESTIMATION_DOMINANT_WARNING`.

Spatially grouped internal holdout (not physical truth) gives MAE 4.329 mm, RMSE 5.234 mm, P95 10.249 mm, maximum 14.928 mm. Gradient/curvature diagnostics pass without isolated spikes. The -9.686 to +18.705 mm field is finite and bounded, unlike the rejected historical unconstrained RBF range -103.177 to +508.741 mm: `NO_GLOBAL_EXTRAPOLATION_BLOWUP`.

## GUI and artifacts

The viewer recognizes `OBSERVED`, `ESTIMATED_LOCAL`, `ESTIMATED_GLOBAL_MODEL` and LOW/MEDIUM/HIGH confidence. Hover displays pixel, H, source, confidence, and XYZ only when direct correspondence is verified. P02-P98 affects color only. NPZ export preserves H, source, confidence, distance-to-support, ROI and validity.

- [calibration package](calibrations/HomeTank_005_demo_only_v1/manifest.yaml)
- [common FOV](demo_common_fov/common_fov.yaml)
- [reference](demo_reference_artifact.yaml)
- [model configuration](demo_full_pixel_config.yaml)
- [result JSON](demo_full_pixel_result/full_pixel_result.json)
- `demo_full_pixel_result/full_pixel_height.npz`
- [height preview](demo_full_pixel_result/full_pixel_height.png)
- [source preview](demo_full_pixel_result/source_status.png)

## Final classifications

`DEMO_ONLY_CALIBRATION_READY`; `DEMO_COMMON_FOV_READY`; `REFERENCE_PLANE_READY_DEMO_ONLY_LOW_CONFIDENCE`; `HOMETANK005_MEASUREMENT_COMPLETED`; `CONSTRAINED_FULL_PIXEL_SURFACE_READY`; `ROI_HEIGHT_COVERAGE_100_PERCENT`; `NO_GLOBAL_EXTRAPOLATION_BLOWUP`; `HOMETANK005_MODEL_ESTIMATED_FULL_PIXEL_DEMO_READY`; `MODEL_ESTIMATION_DOMINANT_WARNING`; `PHYSICAL_ACCURACY_NOT_ESTABLISHED`.

The Windows onedir package was rebuilt at `dist/StereoWaveHeightDemo/StereoWaveHeightDemo.exe`. Startup/no-console process smoke passed, HomeTank_005 resources were present, eight distributed ROI hover queries returned finite H with correct global-model provenance/confidence, and a temporary full artifact export roundtrip passed. This automated smoke does not claim that every manual GUI gesture was exercised by a human operator.
