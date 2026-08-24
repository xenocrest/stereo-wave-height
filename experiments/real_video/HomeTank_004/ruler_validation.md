# HomeTank_004 Ruler-Based Physical Validation

## 1. Purpose and inputs

This module establishes an independent physical-reference method for validating stereo scale, static stability and water height. It is camera-independent and intended to migrate unchanged to a synchronized industrial stereo rig. It does not modify OpenCV `K/D/R/T`, manual geometry, WASS, historical XYZ results, or height values.

Inputs reviewed:

- HomeTank_004 static and wave videos;
- unchanged [OpenCV calibration result](calibration_result.yaml);
- repository-external static and wave XYZ/height products;
- the user-reported fixed vertical ruler with 1 mm minor divisions and 10 mm major divisions.

Final status: **`RULER_VALIDATION_INCOMPLETE_MANUAL_REFERENCE_REQUIRED`**.

## 2. Ruler observation status

The right rectified camera clearly shows the vertical ruler. In the reviewed left rectified frames, the ruler is at the extreme right boundary or the same labelled interval cannot be confirmed. The existing pipeline stores XYZ coordinates but not the source-pixel index for each XYZ point. Therefore an identical physical ruler segment cannot yet be selected in both images and linked to its reconstructed endpoints.

| Item | Value |
|---|---|
| reference type | fixed vertical ruler |
| smallest division | 1 mm |
| major division | 10 mm |
| cam1/right visibility | visible |
| cam0/left visibility | partial/edge, common marks unconfirmed |
| canonical ROI | `MANUAL_ROI_REQUIRED` |
| common stereo endpoints | `NOT_CONFIRMED` |
| pixel-to-XYZ association | unavailable in existing output |

No ROI coordinates or ruler readings are guessed from visual inspection. The pending fields are recorded as `null` in [ruler_reference.yaml](ruler_reference.yaml).

## 3. Three-dimensional scale validation

For manually registered endpoints $P_a$ and $P_b$ separated by known length $L_{real}$, the module computes

$$
L_{reconstructed}=\lVert P_b-P_a\rVert_2,
$$

$$
e_{scale}=\frac{L_{reconstructed}-L_{real}}{L_{real}}.
$$

| Item | Value |
|---|---:|
| real interval | `NOT_AVAILABLE` |
| reconstructed interval | `NOT_AVAILABLE` |
| relative scale error | `NOT_AVAILABLE` |

The printed 1 mm/10 mm division specification alone is insufficient: a particular pair of labelled marks must be identified in both cameras and associated with reconstructed points. Existing point clouds are not rescaled to force agreement.

## 4. Water-height validation

Water height is evaluated along the declared water-plane normal, never by camera Z alone:

$$
h=\frac{n\cdot(P-P_0)}{\lVert n\rVert}.
$$

| Frame | Ruler height | Reconstructed height | Error |
|---|---:|---:|---:|
| — | `NOT_AVAILABLE` | `NOT_AVAILABLE` | `NOT_AVAILABLE` |

Timestamped ruler waterline readings have not yet been registered. Consequently, the existing wave heights remain unchanged and cannot be physically validated in this task.

## 5. Drift classification

The implemented decision interface supports the requested evidence classes:

- moving 3-D ruler position with stable length: `GLOBAL_RECONSTRUCTION_DRIFT`;
- stable ruler position/scale with anomalous water surface: `SURFACE_MATCHING_INSTABILITY`;
- changing ruler length ratio: `GEOMETRIC_SCALE_ERROR`.

HomeTank_004 cannot yet enter A/B/C because the ruler-to-XYZ association is absent. Its current classification is **`RULER_VALIDATION_INCOMPLETE_MANUAL_REFERENCE_REQUIRED`**, not one of the three causal diagnoses.

## 6. Minimum completion step

1. In canonical left and right frames, manually register ROIs containing the same labelled ruler interval.
2. Record two identical physical tick endpoints, their real separation, camera role, frame ID and timestamp.
3. Preserve or export pixel-to-XYZ correspondence for those endpoints without modifying the reconstructed coordinates.
4. Record the ruler waterline for each evaluated static/wave timestamp.
5. Freeze physical drift/scale decision thresholds before examining the resulting errors.

This is annotation and provenance work, not recalibration or result fitting. Once supplied, the generic module can compute scale error, plane-normal water-height error and evidence-based drift classification for this or a future professional stereo system.
