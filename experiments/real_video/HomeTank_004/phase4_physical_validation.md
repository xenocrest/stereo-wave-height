# HomeTank_004 Phase 4 Independent Physical Validation

Status: `PHYSICAL_VALIDATION_COMPLETED_WITH_WARNING`

Classification: `PHYSICAL_VALIDATION_COMPLETED_BUT_REFERENCE_CHANGE_TOO_SMALL_FOR_STRONG_ACCURACY_CLAIM`

## Scope and frozen identity

This is a downstream-only comparison. It did not rerun WASS or change calibration, synchronization, frame selection, rectification, matching, XYZ, reference plane, height arrays, or QA. The Static and Wave height-array hashes remain `B57113...46FF9D` and `BD99D...BC7E10`, exactly matching [phase4_validation_baseline.yaml](phase4_validation_baseline.yaml).

The user-confirmed canonical cam1 pixels are `(798, 414)` for Static and `(800, 414)` for Wave, both with ±1 px localization uncertainty. Frozen two-stage OpenCV mapping gives rectified pixels `(1045.086320, 442.407160)` and `(1049.839779, 443.029746)`. The mapping diagnostic maximum is `0.0001508 px`, negligible relative to the manual ±1 px uncertainty.

## Validation-only support policy

No height value was inspected when choosing the query policy. The center-query nearest distances are 0.0762 px (Static) and 1.5181 px (Wave). A 2 px distance gate is the smallest integer gate that covers both and equals twice the manual uncertainty. A fixed 3 px neighborhood—three times the manual uncertainty—contains 126 and 30 original frozen observations. No interpolation or point creation is performed.

| Readout | Static | Wave |
|---|---:|---:|
| Requested rectified pixel | (1045.0863, 442.4072) | (1049.8398, 443.0297) |
| Nearest observed pixel | (1045.0395, 442.3471) | (1051.3540, 442.9217) |
| Nearest distance | 0.0762 px | 1.5181 px |
| Nearest H | 0.1123 mm | -5.7151 mm |
| Local point count | 126 | 30 |
| Local median H | 0.0500 mm | -5.7172 mm |
| Local MAD / std | 0.1091 / 0.1967 mm | 0.0158 / 0.0203 mm |
| Local P5 / P95 | -0.1718 / 0.4730 mm | -5.7578 / -5.6943 mm |

Nearest XYZ values are `(-0.064510, -0.065954, 0.291430) m` and `(-0.062951, -0.062361, 0.277221) m` respectively.

## Independent change comparison

The ruler readings are absolute scale readings, not direct values in the frozen reference-plane coordinate. Therefore the comparison uses change only:

\[
\Delta H_{ruler}=9.2-9.1=+0.1\ \mathrm{mm}
\]

\[
\Delta H_{stereo}=H_{wave,local}-H_{static,local}=-5.7672\ \mathrm{mm}
\]

The signed discrepancy is `-5.8672 mm`; its absolute value is `5.8672 mm`. Relative error is intentionally `null` because a percentage relative to a 0.1 mm reference change is physically misleading.

The independent ruler uncertainties remain ±1 mm and ±2 mm. Assuming independence only as a descriptive calculation gives an RSS delta uncertainty of 2.236 mm; this is not a confidence interval. The 0.1 mm reference change is far below that uncertainty, so this sample does not establish physical accuracy even though it records the actual frozen-result discrepancy.

## Pixel-location sensitivity

The center result was retained; no perturbed point was selected to improve agreement. Mapping the canonical 3×3 neighborhood produced these local-median ranges:

- Static: -0.0866 to 0.5237 mm (range 0.6103 mm); all nine queries supported.
- Wave: -5.7934 to -5.6810 mm (range 0.1124 mm); seven queries passed the 2 px nearest gate, two had no sufficiently close observation, and one passing query had only 17 local points.

The result is therefore also marked with a Wave support-sensitivity warning. Ruler uncertainty, pixel sensitivity, local stereo spread, and numerical mapping error are reported separately; no unsupported combined uncertainty is manufactured.

## Conclusion

The first frozen Phase 4 independent comparison is complete. It found a stereo local change of `-5.7672 mm` versus the independently read `+0.1 mm`, a signed discrepancy of `-5.8672 mm`. This is recorded without tuning or concealment. Because the manual reference change is much smaller than its uncertainty and Wave support is locally sparse under ±1 px perturbations, the result cannot support a millimetre-accuracy claim. A later, separately frozen validation case should use a physically larger independently observed water-level change; the present baseline must remain unchanged.
