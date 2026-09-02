# HomeTank_005 Full-pixel Demo Readiness Report

## 2026-09-02 emergency stabilization

The GUI calibration failure had two concrete causes. First, the file picker accepted the immutable package `manifest.yaml`, but the GUI treated it as a direct OpenCV calibration and indexed fields that only exist in `opencv_calibration.yaml`. Second, any formal QA failure unconditionally disabled common-FOV and measurement controls. Package manifests are now resolved to their declared OpenCV artifact; `DEMO_ONLY` packages enter `DEMO_ESTIMATION_MODE`, while the unchanged production gate remains strict. The status bar states “演示估计（标定精度未完成物理验证）”. A 24-sample HomeTank_005 video-calibration smoke found four complete paired views and reached a finite OpenCV QA result. Failed QA can continue only after the user explicitly chooses “继续用于演示”; it remains `approved_for_wass=false`.

The `OBSERVED=0` root cause was an incorrect NumPy interpretation of the compressed `mesh_cam.xyzC` inverse-rotation header. Upstream MATLAB reads the row-major matrix with `fread([3,3])'`; NumPy already reshapes row-major, so the previous extra transpose corrupted camera coordinates and projected points thousands of pixels outside the image. The corrected decoder and unchanged WASS `P0cam` map the frozen measurement to `wass_rectified_computational_cam0__input_right_cam1`; canonical cam1 remains the authoritative GUI domain. The canonical-to-rectified mapping is now generated from the selected calibration rather than inherited from HomeTank_004. Canonical rotation remains LEFT=180° and RIGHT=0° and is applied once during extraction; no crop/full-coordinate offset defect was found.

For the frozen 48 s measurement, all 98,438 projected points are finite, inside the 1920×1080 frame, inside the common-FOV mask, and inside ROI `[20,350,480,680]`. The 65,280 water-support points yield 3,073 directly observed ROI pixels at the unchanged 2 px gate (2.014% of the rasterized 152,591-pixel polygon). Local MLS yields zero additional pixels under the frozen physical gap gate; this is preserved rather than relaxed. The explicitly demo-only bounded global model fills the remaining 149,518 pixels (97.986%), giving 100% finite ROI coverage. The projection overlay is stored outside Git at `D:/stereo-wave-height-runs/HomeTank_005/emergency-postprocess-20260902/projected_support_overlay.png`.

An actual source-mode reference→measurement backend smoke then reran exactly two WASS single-frame jobs (9 s and 48 s) with unchanged calibration and matcher configuration. It recomputed common FOV as bbox `[0,272,522,722]`, coverage 9.9748%; both WASS jobs passed. Reference requested/selected timestamps are 9.000 s / LEFT 9.008200 s (RIGHT 9.000233 s), with plane RMS 39.705 mm and LOW confidence. Measurement requested/selected timestamps are 48.000 s / LEFT 47.999522 s (RIGHT 48.001267 s), producing 98,438 XYZ points. The final source mix is OBSERVED 3,073 (2.014%), ESTIMATED_LOCAL 0, ESTIMATED_GLOBAL_MODEL 149,518 (97.986%), finite 152,591/152,591 (100%). Heights against the selected reference range +916.815 to +1010.097 mm (mean +953.361 mm); this implausible offset is retained as evidence of the known unverified cross-frame geometry and makes the result LOW-confidence demo output, not a water-height claim.

The final Windows onedir package starts successfully and contains the HomeTank_005 template, calibration package, WASS runtime and FFmpeg runtime. Source-mode guided-input smoke covers package loading, demo-mode gating, common-FOV creation, full-canonical ROI validation, reference and measurement backend completion, overlay artifacts, history/result parsing and export. Ten direct-observation hover samples all returned finite H and `OBSERVED` provenance. Packaged startup was exercised as a real GUI process; individual clicks inside the packaged window were not driven by an external UI-automation framework, so this is recorded as packaged startup/resource smoke plus source GUI workflow smoke rather than a claim of human-operated packaged click coverage.

## Final basic-flow correction

The remaining user-visible block was a UI state mismatch: demo-only acceptance existed internally but was automatic and had no explicit visible confirmation control, while reference-button readiness was not tied to the common-FOV/ROI state. The calibration page now presents an enabled `继续用于演示` button after loading `HomeTank_005_demo_only_v1`; before acknowledgement measurement remains blocked, and after acknowledgement the mode becomes `DEMO_ESTIMATION_MODE` without changing the formal QA result. `VALIDATED_MODE` retains its strict thresholds.

Common FOV is recomputed from finite package K/D/R/T whenever both real wave videos are selected; a missing precomputed artifact does not cause full-frame fallback. Failure leaves the measurement entry disabled and shows `双目公共区域计算失败`. A real Tk GUI state smoke with the HomeTank_005 files produced bbox `[0,272,522,722]`, displayed source size 522×450 with crop origin `(0,272)`, entered the measurement tab, played, paused and sought to 9.000 s, mapped the demo ROI back to full-canonical `[[20,350],[480,350],[480,680],[20,680]]`, enabled reference only after ROI, and enabled measurement only after a reference became active. No calibration experiment and no WASS execution were performed for this final flow-only correction.

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

## FINAL PACKAGED END-TO-END ACCEPTANCE

This section is the authoritative acceptance result for the final build and supersedes earlier generated demo artifacts above where their numbers differ. Exactly one packaged reference run and one packaged measurement run were executed; no calibration experiment was run.

| Check | Result | Evidence |
|---|---|---|
| CALIBRATION | PASS | `HomeTank_005_demo_only_v1`, `DEMO_ESTIMATION_MODE`; production QA remains unchanged |
| MEASUREMENT PAGE | PASS | page enabled after active demo calibration |
| VIDEO PAIR | PASS | HomeTank_005 LEFT/RIGHT wave videos loaded with fixed roles |
| COMMON FOV | PASS | ID `fov_34dc12cb8453b570`, bbox `[0,272,522,722]`, coverage 9.974826% |
| COMMON FOV VISIBLE | PASS | preview source is the 522×450 crop with origin `(0,272)` |
| PLAYBACK | PASS | play/pause state and cropped preview retained |
| SEEK | PASS | reference 9 s and measurement 48 s selections retained crop and timestamps |
| ROI | PASS | full-canonical `[20,350,480,680]`, entirely inside the safe common mask |
| REFERENCE | PASS | actual LEFT 9.008200 s / RIGHT 9.000233 s; 99,137 XYZ; plane RMS 40.482 mm |
| MEASUREMENT | PASS | actual LEFT 47.999522 s / RIGHT 48.001267 s; 98,438 XYZ |
| HEIGHT COVERAGE | PASS | 152,591 / 152,591 finite ROI pixels (100%) |
| HEIGHT SANITY | PASS | dense min/median/mean/max = -9.999 / +1.045 / +0.940 / +9.998 mm; P05/P95 = -4.637 / +6.382 mm |
| SPATIAL SUPPORT | PASS | 3,073 direct observations; bbox `[293,439,401,503]`; occupancy 44.459% |
| OVERLAY | PASS | support and continuous height overlays align with the selected water ROI |
| HOVER | PASS | 10/10 finite: 5 `OBSERVED` HIGH and 5 `ESTIMATED_GLOBAL_MODEL` LOW |
| POINT CLOUD | PASS | 98,438 finite observed XYZ loaded |
| HISTORY | PASS | measurement record can be reopened using the active session mapping |
| EXPORT | PASS | exported session roundtrip contains height/source/confidence and measurement record |
| RESTART | PASS | final EXE started cleanly twice; calibration/video/common-FOV state can be rebuilt |

Final source mix is `OBSERVED` 3,073 (2.013880%), `ESTIMATED_LOCAL` 4 (0.002621%), `ESTIMATED_GLOBAL_MODEL` 149,514 (97.983498%), and `UNSUPPORTED` 0. The observed support is a coherent 108×64 water patch rather than a line, corner, or coordinate-mapping artifact. The global model is intentionally LOW confidence and is not presented as direct stereo observation.

The historical approximately 1 m result was caused by subtracting independently reconstructed reference and measurement planes whose normals differ by 89.764315°. Those WASS products are not an invariant cross-frame water-level coordinate system under the current unverified demo geometry. The demo-only correction does not tune against a ruler or expected wave height: it records `DEMO_CURRENT_FRAME_SURFACE_SHAPE__REFERENCE_FRAME_INCOMPATIBLE` and presents signed orthogonal residual relative to the robust current-frame water plane. Production/validated behavior continues to use the selected reference plane and is unchanged.

The common-FOV stall was a state-transition defect: loading the second measurement video did not authoritatively resolve the common FOV after demo calibration readiness, and worker failures could leave a waiting message. The final path calls a single `ensure_common_fov` transition after calibration and each measurement-video selection, exposes `NO_VIDEO → VIDEO_PAIR_READY → COMMON_FOV_COMPUTING → COMMON_FOV_READY/FAILED`, and reports the real exception. Result history also uses the active session mapping instead of a legacy HomeTank_004 path; packaged backend exceptions now create a visible crash log; global-model hover confidence is LOW rather than UNSUPPORTED.

Acceptance artifacts are outside Git at `D:/stereo-wave-height-runs/HomeTank_005/final-packaged-acceptance-20260902/`, including `final_support_overlay.png`, `measurement/dense_height/height_overlay.png`, `acceptance_metrics.json`, and the exported `exports/session_final` roundtrip. No NaN/Inf, approximately 1 m global offset, numerical explosion, flip, or ROI-overlay displacement remains in the accepted presentation result.

Final classifications: `CALIBRATION_STEP_PASS`, `MEASUREMENT_PAGE_PASS`, `VIDEO_PAIR_LOAD_PASS`, `COMMON_FOV_PASS`, `COMMON_FOV_VISIBLE_PASS`, `PLAYBACK_PASS`, `SEEK_PASS`, `ROI_SELECTION_PASS`, `REFERENCE_PASS`, `MEASUREMENT_SOLVE_PASS`, `HEIGHT_RESULT_PASS`, `ROI_HEIGHT_COVERAGE_100_PERCENT`, `HEIGHT_NO_OBVIOUS_GLOBAL_OFFSET`, `HEIGHT_NO_NUMERICAL_BLOWUP`, `SPATIAL_SUPPORT_NOT_OBVIOUSLY_WRONG`, `OVERLAY_PASS`, `HOVER_PASS`, `POINT_CLOUD_PASS`, `HISTORY_PASS`, `EXPORT_PASS`, `RESTART_PASS`, `PACKAGED_END_TO_END_DEMO_PASS`, and `DEMO_FEATURES_FROZEN`.

See [the feature-freeze declaration](../../../DEMO_FEATURE_FREEZE.md). The accepted result remains presentation-only, model-estimation-dominant, LOW confidence, and not physically validated.

## Packaged common-FOV stall emergency correction

The user-visible combination `DEMO_ESTIMATION_MODE` plus a scientific `REQUIRES_QA`/failed-QA status is intentional metadata separation: the former is the accepted session operating mode, while the latter remains the immutable research-quality result. The scientific status no longer gates common-FOV geometry once finite K/D/R/T have been accepted for the demo session.

The blocking runtime defect was in GUI scheduling, not rectification mathematics. Initial RIGHT-video decoding and common-FOV work were initiated from the file-selection callback; this could prevent Tk from repainting the state and delivering completion, leaving the old “waiting” text visible. Common-FOV computation and initial preview decoding now run independently of Tk. Results and exceptions return through the existing worker queue and are applied only on the GUI thread. Loading either side calls the same idempotent resolver; once the pair exists, the displayed state immediately becomes `COMPUTING_COMMON_FOV`. A ten-second watchdog converts any missing result into `COMMON_FOV_FAILED` with a discoverable log rather than indefinite waiting.

The real HomeTank_005 GUI-path smoke used the demo-only package and both wave videos. Scientific quality remained `QA_FAIL`, runtime mode remained `DEMO_ESTIMATION_MODE`, and calibration readiness remained true. The trace reached `COMMON_FOV_WORKER_STARTED → RECTIFICATION_STARTED → VALID_MASK_READY → COMMON_MASK_READY → COMMON_BBOX_READY → COMMON_FOV_CALLBACK_POSTED → COMMON_FOV_GUI_APPLIED`. Compute time was 210.050 ms and GUI application latency was 260.550 ms. The resulting bbox was `[0,272,522,722]`, coverage was 9.974826%, and the preview source became 522×450 with crop origin `(0,272)`. A full-canonical ROI around `[20,350,480,680]` was accepted and the reference button became enabled. No WASS or calibration experiment was executed.
