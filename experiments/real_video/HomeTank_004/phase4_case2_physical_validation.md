# HomeTank_004 Phase 4 Case 2 Independent Physical Validation

Status: `PHYSICAL_VALIDATION_BLOCKED_AT_LOCAL_OBSERVATION_QUERY`

Classification: `CASE2_PIXEL_XYZ_DISTANCE_GATE_FAIL`

## Independent inputs and frozen boundary

The user confirmed Static `9.1 ± 1.0 mm` at canonical cam1 `(798,414)` and Case 2 Wave `9.6 ± 1.0 mm` at `(799,396)`. The Wave waterline was described as basically clear. These inputs are manual downstream references only.

Before reading the frozen arrays, SHA-256 was verified for the Case 2 height NPZ, pixel–XYZ NPZ, XYZ text, `mesh_cam.xyzC`, and full-resolution canonical cam1 PNG. All five match [the frozen baseline](phase4_validation_case2_baseline.yaml). WASS was not rerun; calibration, rectification, reference plane, height definition and reconstruction parameters remain unchanged.

## Mapping and strict observed-point query

The existing two-stage OpenCV 4.6 mapping converts canonical `(799,396)` to computational rectified `(1053.399225,402.455963)`. The forward-map roundtrip error is `0.00001268 px`, consistent with the frozen mapping regression. No resize, homography, crop adjustment or manual offset was used.

The unchanged query requires a nearest original observation within `2 px`, then reports original observations within a `3 px` radius without interpolation. The nearest frozen pixel is `(1058.442409,417.106881)`, distance `15.494616 px`; it therefore fails the gate. Its XYZ `(-0.061204,-0.062339,0.255616) m` and height `-24.453754 mm` are retained only as diagnostic nearest-candidate metadata and are **not** accepted as the ruler-adjacent measurement. There are zero observations within the 3 px neighborhood.

All nine canonical ±1 px sensitivity locations also fail the same 2 px gate. Their nearest distances span `12.481628–18.559964 px`; consequently no local median range exists. The center result was not replaced by a more favorable neighboring point.

## Physical comparison outcome

The independent ruler change is `+0.5 mm`. Its descriptive independent RSS uncertainty is `sqrt(1²+1²) = 1.414214 mm`, not a confidence interval; signal/RSS is `0.3536`. This reference remains small relative to manual reading uncertainty.

Because the formal Case 2 Wave local query fails, Wave local median H, `ΔH_stereo`, signed error and absolute error are all null. Relative error is also null, with reason `RELATIVE_ERROR_NOT_MEANINGFUL_WHEN_REFERENCE_CHANGE_IS_SMALL_RELATIVE_TO_MEASUREMENT_UNCERTAINTY`. No accuracy pass or fail is asserted.

The frozen global median `-24.7038 mm`, mean `-24.3863 mm`, and RMS `24.4070 mm` describe the reconstructed support as a whole. They cannot replace a missing ruler-adjacent local observation, so this case does not establish whether that global offset is present at the manually selected waterline.

## Case 1 preservation and conclusion

Case 1 remains unchanged: ruler delta `+0.1 mm`, stereo delta `-5.767183 mm`, absolute discrepancy `5.867183 mm`, and classification `PHYSICAL_VALIDATION_COMPLETED_BUT_REFERENCE_CHANGE_TOO_SMALL_FOR_STRONG_ACCURACY_CLAIM`.

Case 2 supplies valid independent manual data and a numerically accurate coordinate mapping, but the frozen reconstruction has no observation close enough to the selected waterline under the pre-existing gate. The result is preserved as a support-location failure, not repaired by wider search, interpolation, candidate replacement or tuning.
