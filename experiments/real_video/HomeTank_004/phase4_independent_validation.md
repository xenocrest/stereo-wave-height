# HomeTank_004 Phase 4 Independent Physical Validation

Status: **`MANUAL_REFERENCE_LOCATION_REQUIRED`**

## Boundary and baseline

This workflow is bound to [phase4_validation_baseline.yaml](phase4_validation_baseline.yaml), whose Static R0 and Wave R0 arrays, calibration identity, synchronization policy and reference-plane source were frozen before ruler data entered the project. No WASS run or frozen result was changed in this work.

The dependency is one-way:

`frozen reconstruction result + manual ruler measurement -> independent validation`

Ruler data never enters calibration, synchronization, WASS, XYZ generation, reference-plane fitting or height calculation. A large future error must be recorded; it must not trigger an automatic correction of this baseline.

## Comparable physical quantity

The algorithm height remains the signed orthogonal distance to the frozen reference plane,

`H(P) = (n dot P + D) / ||n||`.

Camera Z is not compared with the ruler. The ruler provides the change between the Wave and Static waterline readings, converted by an explicitly declared scale direction to the same positive plane-normal convention. The algorithm comparison is a local readout near the manually annotated waterline pixel, not the whole-surface mean.

## Readout policy

- Query only existing frozen pixel–XYZ/height observations.
- Reject a query outside an explicit nearest-distance gate; do not interpolate.
- Save nearest-point height for traceability.
- Use local median height as the comparison value only when the explicitly configured neighborhood has sufficient support.
- Save neighborhood point count, radius and median absolute deviation as local spread.

The distance gate, neighborhood radius and minimum point count remain `null`: the manual pixel uncertainty and local sampling density needed to justify them have not yet been supplied.

## Error and uncertainty

With aligned signs, `e = H_stereo_local - delta_H_ruler`; absolute error is `|e|`. Relative error is `100 |e| / |delta_H_ruler|` only outside an explicit near-zero reference gate. Otherwise it is `null` with `RELATIVE_ERROR_NOT_MEANINGFUL_NEAR_ZERO_REFERENCE`.

Ruler reading uncertainty, pixel-location sensitivity and local stereo spread are reported separately. No combined uncertainty is fabricated without a justified model.

## Frozen cam1 reference mapping

The user selected `cam1`. In both frozen R0 runs WASS logged `auto-swapping left-right images`; therefore computational cam0 is the original input-right/cam1 image. The frozen pixel–XYZ system is `wass_rectified_computational_cam0__input_right`. The exported `*_cam1_reference.png` files are exact copies of the frozen `rectified/000000_right.png` outputs, so clicks on them are direct coordinates in the pixel–XYZ system. No resizing, homography or newly derived rectification is used. The `*_canonical.png` copies are identity aids only and must not be clicked for XYZ lookup.

## Current result

The user supplied Static `9.1 ± 1.0 mm`, Wave `9.2 ± 2.0 mm`, camera `cam1`, and reported that ruler values increase upward. The nominal reading difference is 0.1 mm, smaller than the individual reading uncertainties, so relative percentage error will not be treated as a stable primary measure. Waterline pixels and their uncertainties remain `null`; therefore no physical error is calculated and physical accuracy remains **`PHYSICAL_ACCURACY_NOT_ESTABLISHED`**. See [manual_ruler_measurement_instructions.md](manual_ruler_measurement_instructions.md) for the two click commands.
