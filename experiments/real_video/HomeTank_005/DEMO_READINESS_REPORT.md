# HomeTank_005 Full-pixel Demo Readiness Report

## 2026-09-02 emergency stabilization

The GUI calibration failure had two concrete causes. First, the file picker accepted the immutable package `manifest.yaml`, but the GUI treated it as a direct OpenCV calibration and indexed fields that only exist in `opencv_calibration.yaml`. Second, any formal QA failure unconditionally disabled common-FOV and measurement controls. Package manifests are now resolved to their declared OpenCV artifact; `DEMO_ONLY` packages enter `DEMO_ESTIMATION_MODE`, while the unchanged production gate remains strict. The status bar states “演示估计（标定精度未完成物理验证）”. A 24-sample HomeTank_005 video-calibration smoke found four complete paired views and reached a finite OpenCV QA result. Failed QA can continue only after the user explicitly chooses “继续用于演示”; it remains `approved_for_wass=false`.

The `OBSERVED=0` root cause was an incorrect NumPy interpretation of the compressed `mesh_cam.xyzC` inverse-rotation header. Upstream MATLAB reads the row-major matrix with `fread([3,3])'`; NumPy already reshapes row-major, so the previous extra transpose corrupted camera coordinates and projected points thousands of pixels outside the image. The corrected decoder and unchanged WASS `P0cam` map the frozen measurement to `wass_rectified_computational_cam0__input_right_cam1`; canonical cam1 remains the authoritative GUI domain. The canonical-to-rectified mapping is now generated from the selected calibration rather than inherited from HomeTank_004. Canonical rotation remains LEFT=180° and RIGHT=0° and is applied once during extraction; no crop/full-coordinate offset defect was found.

For the frozen 48 s measurement, all 98,438 projected points are finite, inside the 1920×1080 frame, inside the common-FOV mask, and inside ROI `[20,350,480,680]`. The 65,280 water-support points yield 3,073 directly observed ROI pixels at the unchanged 2 px gate (2.014% of the rasterized 152,591-pixel polygon). Local MLS yields zero additional pixels under the frozen physical gap gate; this is preserved rather than relaxed. The explicitly demo-only bounded global model fills the remaining 149,518 pixels (97.986%), giving 100% finite ROI coverage. The projection overlay is stored outside Git at `D:/stereo-wave-height-runs/HomeTank_005/emergency-postprocess-20260902/projected_support_overlay.png`.

An actual source-mode reference→measurement backend smoke then reran exactly two WASS single-frame jobs (9 s and 48 s) with unchanged calibration and matcher configuration. It recomputed common FOV as bbox `[0,272,522,722]`, coverage 9.9748%; both WASS jobs passed. Reference requested/selected timestamps are 9.000 s / LEFT 9.008200 s (RIGHT 9.000233 s), with plane RMS 39.705 mm and LOW confidence. Measurement requested/selected timestamps are 48.000 s / LEFT 47.999522 s (RIGHT 48.001267 s), producing 98,438 XYZ points. The final source mix is OBSERVED 3,073 (2.014%), ESTIMATED_LOCAL 0, ESTIMATED_GLOBAL_MODEL 149,518 (97.986%), finite 152,591/152,591 (100%). Heights against the selected reference range +916.815 to +1010.097 mm (mean +953.361 mm); this implausible offset is retained as evidence of the known unverified cross-frame geometry and makes the result LOW-confidence demo output, not a water-height claim.

The final Windows onedir package starts successfully and contains the HomeTank_005 template, calibration package, WASS runtime and FFmpeg runtime. Source-mode guided-input smoke covers package loading, demo-mode gating, common-FOV creation, full-canonical ROI validation, reference and measurement backend completion, overlay artifacts, history/result parsing and export. Ten direct-observation hover samples all returned finite H and `OBSERVED` provenance. Packaged startup was exercised as a real GUI process; individual clicks inside the packaged window were not driven by an external UI-automation framework, so this is recorded as packaged startup/resource smoke plus source GUI workflow smoke rather than a claim of human-operated packaged click coverage.

The reference and measurement runs use identical calibration XML hashes, identical `P0cam`, the same scale, camera auto-swap and metric camera-frame convention. No autocalibration ran and no additional per-run centering was retained after the official xyzC inverse transform. However, their independently matched surfaces remain mutually inconsistent under the unverified demo geometry; the 40.502 mm reference-plane RMS warning is unchanged. Consequently quality remains `DEMO_ONLY_GEOMETRY_UNVERIFIED` / LOW confidence and no physical-accuracy claim is made.

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
