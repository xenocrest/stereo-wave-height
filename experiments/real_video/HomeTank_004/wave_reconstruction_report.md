# HomeTank_004 Wave Reconstruction Report

## 1. Scope

This is the first real-video wave time-series pipeline closure for HomeTank_004. It reuses the general reconstruction entry and does not add phone-model compensation, modify OpenCV `K/D/R/T`, replace calibrated T with manual geometry, run autocalibration, change WASS parameters, or develop a GUI.

Final status: **`WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING`**.

This means the five configured wave pairs completed the software chain. It does not mean the recovered heights are metrically accepted: the static reference remains `STATIC_VALIDATION_FAIL`, calibration retains its recorded quality warning, and wave synchronization is still a medium-confidence candidate.

## 2. Input and timing

| Field | Value |
|---|---|
| left input role | cam0 / LEFT |
| right input role | cam1 / RIGHT |
| source | `videos/wave/` MP4 pair |
| resolution | 1920×1080 px |
| source duration | approximately 161.17 s per stream |
| processed interval | 20.0–20.4 s |
| sample spacing | 0.1 s |
| processed frames | 5 |
| pairing | explicit timestamps; cam1−cam0 candidate offset 0.0 s |
| synchronization confidence | MEDIUM, candidate only |

Equal configured timestamps follow the existing wave synchronization preanalysis; they are not evidence of hardware synchronization. Source videos were not modified.

## 3. Fixed reconstruction inputs

- Calibration source: unchanged OpenCV `K0/D0/K1/D1/R/T` in `calibration_result.yaml`.
- Metric baseline: `0.06868471158474378 m`, from the norm of calibrated T.
- WASS chain: prepare → match → restore fixed R/T → stereo.
- Autocalibration: not run.
- Manual baseline/extrinsics: not used.
- Static reference: [static_reference_plane.yaml](static_reference_plane.yaml), derived from static frame 000000 in the preceding pipeline run.

The reference plane is:

$$
(0.4266091)X+(0.0675784)Y+(0.9019079)Z-0.2246730=0.
$$

Its own residual RMS was 1.5508 mm, but the three-frame static baseline failed stability. The same plane is nevertheless held fixed here so wave frames are not independently zeroed.

## 4. WASS and height results

All five frames passed prepare, match and stereo. The repository-external output is:

`D:/stereo-wave-height-runs/HomeTank_004/wave-reconstruction-pipeline-20260824`

| Frame | XYZ points | Valid triangulated | Water points | Own-plane RMS (mm) | H mean (mm) | H RMS (mm) | H max abs (mm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 000000 | 142,444 | 388,293 | 142,201 | 2.0030 | 22.4403 | 22.5445 | 49.6534 |
| 000001 | 221,307 | 412,605 | 219,463 | 2.7764 | -7.0403 | 7.6161 | 35.1863 |
| 000002 | 191,312 | 375,753 | 189,723 | 3.5603 | -11.8592 | 12.4086 | 47.2694 |
| 000003 | 201,904 | 380,283 | 200,088 | 3.0355 | -0.0279 | 3.0900 | 93.1372 |
| 000004 | 198,554 | 383,136 | 197,070 | 2.3643 | -20.9202 | 21.0804 | 38.6987 |

Total XYZ points: **955,521**. Across all pointwise height samples, the range is `[-0.026767, 0.093137] m`.

`water points` are points within the configured 10 mm diagnostic gate of each frame's fitted plane. Heights are not measured from those per-frame planes: every H value is the signed distance to the single static reference plane above.

## 5. Disparity output boundary

The frozen WASS runtime does not export its lossless numeric SGBM disparity array. For each frame, `reconstruction_result.json` therefore records:

- valid triangulated count from the WASS log;
- mean/std/min/max of the saved 8-bit disparity visualization;
- `absolute_numeric_status = NOT_EXPORTED_BY_FROZEN_WASS_RUNTIME`.

The normalized visualization is saved for QA but is not mislabeled as physical pixel disparity. No numeric disparity range is guessed from it.

## 6. Generated artifacts

The repository-external run contains:

- five timestamp-paired canonical image pairs;
- five rectified left/right pairs restored to input camera roles;
- five WASS disparity QA images;
- five metric XYZ and PLY point clouds;
- five compressed irregular `(X,Y,H)` height products;
- `reconstruction_result.json` for future GUI consumption;
- automatic `reconstruction_report.md` and complete WASS logs.

No large artifact is committed to Git.

## 7. Conclusion

The real wave video chain is operational from configured MP4 timestamps through WASS point clouds to a shared-reference time series of height samples. The status is deliberately not `PASS` for physical wave measurement:

- pipeline closure: `PASS`;
- wave pipeline: `WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING`;
- static reference stability: `FAIL_PRESERVED`;
- synchronization: `CANDIDATE_ONLY`;
- industrial accuracy: `NOT_ESTABLISHED`.

The current H statistics combine possible wave motion with known reference, calibration, synchronization and matching uncertainty. They must not be reported as validated wave height. The next engineering step is a professional synchronized stereo deployment with a stable static reference and independent physical wave-height validation, using the same configuration and result interfaces.
