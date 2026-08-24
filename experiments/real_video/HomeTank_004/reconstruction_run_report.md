# HomeTank_004 End-to-End Reconstruction Run

## 1. Purpose and boundary

This run validates the reusable orchestration path

```text
timestamp-paired stereo video
  -> canonical frame extraction
  -> unchanged OpenCV K/D/R/T validation
  -> WASS prepare/match/fixed-R/T stereo
  -> metric XYZ/PLY
  -> plane extraction
  -> first-static-plane reference
  -> irregular (X,Y,H) height samples
  -> JSON/Markdown result
```

HomeTank_004 is an input case, not a phone-specific implementation. The run verifies software closure only; it does not establish industrial accuracy, change `CALIBRATION_QUALITY_FAIL`, or change `STATIC_VALIDATION_FAIL`. Manual geometry was not used for reconstruction, autocalibration and wave were not run, and no WASS matching/reconstruction algorithm was implemented in this project.

## 2. Configuration

The committed entry configuration is [reconstruction_pipeline.yaml](reconstruction_pipeline.yaml). Machine-local executable/config/output paths are supplied through environment variables; camera model names and absolute video paths are not embedded in pipeline code.

| Item | Frozen value/source |
|---|---|
| input | HomeTank_004 static left/right videos |
| pairs | 3 timestamp-associated pairs at the previously registered PTS values |
| calibration | unchanged OpenCV `K0/D0/K1/D1/R/T` from `calibration_result.yaml` |
| calibrated baseline | 0.06868471158474378 m, norm of calibrated T |
| quality mode | `diagnostic_allow_failed_gate`; original `approved_for_wass=false` is retained |
| rectification | alpha 0, zero disparity, from the frozen WASS config |
| WASS path | prepare → match → restore fixed R/T → stereo |
| autocalibration | not run |
| surface output gate | 0.010 m diagnostic point-to-fitted-plane mask threshold |
| height reference | fitted plane from static frame 000000, shared by all frames |

The first invocation with the repository's production-runtime example failed fast because that executable does not recognize `RECTIFICATION_ALPHA`. No parameter was changed. The successful invocation used the same isolated policy-capable WASS 1.11 build that produced the prior static closure; the runtime binding is machine-local and not committed. This distinction is preserved rather than presenting the failed invocation as successful.

## 3. Run status and artifacts

Final external output directory:

`D:/stereo-wave-height-runs/HomeTank_004/reconstruction-pipeline-20260824-retry2`

Status: `COMPLETED_DIAGNOSTIC_STATIC_UNSTABLE`.

Generated outside Git:

- `rectified/`: three original-role left/right rectified PNG pairs;
- `disparity/`: three WASS 8-bit diagnostic disparity visualizations;
- `pointcloud/`: metric XYZ and PLY for each frame;
- `height/`: compressed irregular `(X,Y,H)` samples and water masks;
- `reconstruction_result.json`: uniform machine-readable GUI boundary;
- `reconstruction_report.md`: automatically generated summary;
- `wass_workspace/logs/`: per-stage argv, stdout, stderr and return status.

The disparity PNG is not described as lossless numeric disparity. The height product is an irregular observed-point field and is not silently interpolated into a regular grid.

## 4. Results

All three frames passed WASS prepare, match and stereo. Fixed OpenCV R/T was restored after match; autocalibration was not called.

| Frame | XYZ points | X range (m) | Y range (m) | Z range (m) | Own-plane RMS (mm) | H range relative to frame 000000 plane (m) |
|---|---:|---|---|---|---:|---|
| 000000 | 211,787 | -0.095723 / -0.013468 | -0.094479 / 0.009040 | 0.276660 / 0.368340 | 1.5508 | -0.002878 / 0.100156 |
| 000001 | 75,471 | -0.179509 / -0.073550 | -0.014008 / 0.032838 | -0.318663 / -0.261233 | 5.9034 | -0.588343 / -0.519056 |
| 000002 | 91,210 | -0.148628 / -0.047600 | 0.006388 / 0.049102 | 0.146822 / 0.207904 | 3.3441 | -0.125329 / -0.081100 |

Total XYZ point count is 378,468. The frame-000000 reference plane is:

$$
(0.4266091)X+(0.0675784)Y+(0.9019079)Z-0.2246730=0.
$$

The global pointwise height range is `[-0.588343, 0.100156] m`. This large static spread, including negative camera-coordinate Z in frame 000001, is a failure signal consistent with the existing cross-frame matching instability. Pipeline closure therefore passes while static stability remains failed.

## 5. Interpretation

This task establishes one command and one result schema from video through WASS XYZ and reference-plane height samples. It does not make the current data metrically acceptable. In particular:

- `pipeline_closure = PASS`;
- `static_stability = FAIL_PRESERVED`;
- `industrial_accuracy = NOT_ESTABLISHED`;
- wave remains not run;
- the calibration quality gate remains recorded as failed despite operational use in this diagnostic run.

For a professional camera, the same entry accepts configured videos/timestamps, approved OpenCV calibration, a verified WASS config/runtime and an external output directory. A regular `H(y,x,t)` grid still requires the already documented official `wassgridsurface` interface; this pipeline does not invent a gridding method.
