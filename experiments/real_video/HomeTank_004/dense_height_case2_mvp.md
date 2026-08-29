# HomeTank_004 Dense Height Map MVP

## Scope

This is a minimal single-frame display artifact built from the frozen Phase 4
Case 2 WASS observations. WASS and reconstruction were not rerun or modified.
It is not an independent physical-accuracy result.

## Frozen input and coordinates

- Frame: `HomeTank_004/wave/phase4_case2_candidate02/frame_000000`.
- Output image coordinates: canonical cam1, 1920 × 1080 px.
- Direct-observation gate: 2 px in the frozen WASS rectified computational-cam0
  image, which is the frozen input-right/cam1 role.
- Metric scale: frozen OpenCV calibrated baseline, 0.0686847 m.
- Height: signed orthogonal distance to the frozen Static R0 reference plane;
  camera Z is not used as height.

Canonical pixels are mapped through the frozen cam1 calibration and WASS
rectification. A calibrated ray is intersected with the static reference plane
to establish the physical coordinate domain. Missing pixels then use the
unchanged local weighted quadratic MLS model in the two metre-valued axes of
that plane, followed by ray/surface intersection.

## Conservative domain and support policy

The demo water ROI is the conservative canonical-cam1 polygon
`[(700,340), (900,340), (900,520), (700,520)]`, selected from visible image
content rather than reconstructed H values. The original observed-convex-hull
mode remains available as the default safety mode.

The frame P90 nearest-neighbour spacing is 0.107233 mm. The largest admitted
continuous hole is `hole_2 = 3 × P90 = 0.321699 mm`. Because discrete support
starts just outside an excluded hole, one P90 sample-spacing allowance is used
when evaluating the nearest surviving sample; this reproduces the validated
hole_2 experiment without admitting hole_3. MLS keeps the frozen 6 × P90
support radius, 3 × P90 Gaussian sigma, 12-point minimum, 64-neighbour maximum,
rank check, and condition-number limit of $10^8$.

## Result

| Item | Result |
|---|---:|
| Water ROI pixels | 36,381 |
| OBSERVED | 1,950 (5.3599%) |
| ESTIMATED | 8 (0.0220%) |
| UNSUPPORTED | 34,423 (94.6181%) |
| Valid H minimum | -25.4970 mm |
| Valid H maximum | -16.7430 mm |
| Valid H mean | -24.3001 mm |
| Valid H median | -24.6615 mm |
| Generation time | 3.7182 s |

The frozen manual point `(799,396)` is inside the polygon but remains
`UNSUPPORTED`; no gate was relaxed and no height was fabricated.

A deterministic 50-point direct-observation hold-out QA supported 49 points
(98.0%), with MAE 0.0849 mm, RMSE 0.3059 mm, and P95 absolute error 0.2383 mm.
This is an implementation regression check against frozen WASS observations,
not physical truth.

Classification: `DENSE_HEIGHT_MAP_MVP_COMPLETED`.

## Outputs

- `dense_height_case2_outputs/dense_height_case2.npz`: real `height_mm`, status,
  valid mask, water ROI mask, and traceability metadata.
- `dense_height_case2_outputs/dense_height_case2.png`: height visualization.
- `dense_height_case2_outputs/dense_height_case2_status.png`: OBSERVED /
  ESTIMATED / UNSUPPORTED visualization.
- `dense_height_case2_outputs/dense_height_case2_result.yaml`: metrics and QA.
