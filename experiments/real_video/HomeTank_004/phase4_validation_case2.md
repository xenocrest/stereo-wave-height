# HomeTank_004 Phase 4 Case 2 Frozen Baseline

Status: `CASE2_MANUAL_REFERENCE_REQUIRED`

## Frozen identity and boundary

The user selected only `candidate_02` from the image-only candidate set. Before execution, its candidate record was matched exactly to requested left time `29.4654055 s`, left R0 `pts_2651866` at `29.465178 s`, cam1/right R0 `pts_2646070` at `29.400778 s`, residual `+1.0055 ms`, canonical cam1 rotation `0°`, and the existing R0 engineering sync policy. No other candidate was reconstructed or compared.

Case 1 remains unchanged: its ruler delta is `+0.1 mm`, absolute discrepancy is `5.867183 mm`, and its classification remains `PHYSICAL_VALIDATION_COMPLETED_BUT_REFERENCE_CHANGE_TOO_SMALL_FOR_STRONG_ACCURACY_CLAIM`. Case 2 reuses the frozen Case 1 Static height array and [Static reference plane](static_reference_plane.yaml); Static was not rerun.

## Formal reconstruction

Exactly one candidate_02 Wave run used the frozen OpenCV K/D/R/T, fixed-calibration WASS path, rectification policy `alpha=0`, zero disparity enabled, existing matcher/stereo configuration, existing pixel–XYZ projection, and the frozen Static reference plane. `wass_autocalibrate` was not run and the Wave plane was not redefined as zero.

| Stage / quantity | Result |
|---|---:|
| prepare / match / stereo | PASS / PASS / PASS |
| retained epipolar matches | 33 |
| total reconstruction time | 26.2935 s |
| triangulated / retained XYZ points | 134,628 / 35,459 |
| pixel–XYZ correspondences | 35,459 |
| XYZ X range | -0.092039 to -0.058490 m |
| XYZ Y range | -0.062339 to -0.036460 m |
| XYZ Z range | 0.253591 to 0.275260 m |

## Read-only height QA

Height is `(n·P + D)/||n||` relative to the unchanged Static reference plane. No clipping, filtering, threshold adjustment, or point deletion was performed.

| Statistic | Value |
|---|---:|
| raw range | -25.5087 to -13.7026 mm |
| mean / median | -24.3863 / -24.7038 mm |
| standard deviation / RMS | 1.0045 / 24.4070 mm |
| P1 / P5 | -25.3387 / -25.1924 mm |
| P95 / P99 | -22.6211 / -20.5246 mm |
| deviation from median >5 mm / >10 mm | 0.4822% / 0.0649% |
| unique observed pixels | 8,399 |

The narrow coherent distribution with a large overall offset does not show an obvious whole-reconstruction numerical collapse. It is not interpreted as physical water-level accuracy or as proof that Case 2 has a sufficiently strong ruler signal.

## Frozen artifacts and manual stop

The complete WASS workspace and large outputs remain outside Git at `D:/stereo-wave-height-runs/HomeTank_004/phase4-case2-candidate02-20260828`. The formal full-resolution, uncropped, unenhanced cam1 canonical image is [wave_case2_cam1_canonical_reference.png](phase4_case2_manual_reference/wave_case2_cam1_canonical_reference.png), identity `pts_2646070`, SHA-256 `1112D9CE...D6415D`. It is distinct from the scaled selection preview.

The [Case 2 baseline](phase4_validation_case2_baseline.yaml) freezes the height, pixel–XYZ, XYZ, mesh and reference-image hashes. The [manual reference record](phase4_case2_ruler_measurement.yaml) retains the existing Static `9.1 ± 1.0 mm` and `(798,414)` click, while all Case 2 Wave ruler/click fields remain null. The existing picker accepts label `wave_case2`.

No physical error is calculated. Work stops pending the user's manual ruler reading and waterline click on the formal canonical image.
