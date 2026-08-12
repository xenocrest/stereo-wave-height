# Case 1 reconstruction-support trace

Run date: 2026-08-11  
Status: **SUPPORT LOSS LOCATED; CASE 1 STILL FAILED; CASE 2 NOT STARTED**

The exact runtime rule and its current observability boundary are recorded in
[`case1_zgap_component_analysis.md`](case1_zgap_component_analysis.md).
The release build did not preserve float pre-cluster depth; no precise Z-gap
statistics or component sizes were inferred from JPEG/PNG.

This report reads the frozen Case 1 images, logs, diagnostics, xyzC and NetCDF.
No WASS/gridder parameter or source was changed and no stage was rerun. Counts
for frames in each identical pair are the same.

## 1. Stage-by-stage count trace

The input image has `2448 x 2048 = 5,013,504` pixels. `prepare` preserves this
size and reports no rejection count. Sparse `match` counts are calibration
matches and are not dense surface-point counts.

| stage | static, per frame | raised, per frame | evidence/meaning |
|---|---:|---:|---|
| left/right textured pixels | 3,883,220 each (77.4552%) | 3,924,668 each (78.2819%) | saved PNG; texture intensities are 16--239, so nonzero equals rendered support |
| same-pixel left/right mask intersection | 3,452,164 (68.8573%) | 3,489,424 (69.6005%) | image-mask diagnostic, not physical correspondence |
| matcher inliers | 989 | 1,647 | `matcher_stats.csv`; sparse autocalibration input |
| final disparity diagnostic nonzero | 89.2399% | 89.5509% | `disparity_final_scaled.png`; visualization only |
| valid triangulated points | 4,322,503 (86.2172%) | 4,331,598 (86.3986%) | `wass_stereo_log.txt` |
| largest Z-gap connected component | 4,311,954 (99.7560% of triangulated) | 1,794,468 (41.4274% of triangulated) | `wass_stereo_log.txt` |
| loss at component extraction | 10,549 | **2,537,130** | exact difference above |
| RANSAC inliers | 4,311,954 | 1,794,468 | all retained-component points |
| after first plane crop | 4,311,954 | 1,794,468 | no additional loss |
| plane-refinement inliers | 4,311,954 | 1,794,468 | no additional loss |
| after final plane crop / xyzC | 4,311,954 | 1,794,468 | no additional loss |
| xyzC points inside final grid | 3,439,690 | 1,697,433 | explicit common transform and grid assignment |
| grid cells with raw support | 25,600/25,600 | 13,171/25,600 | 100% versus 51.4492% |

The decisive upstream loss is therefore exactly the post-triangulation
`cluster_biggest_connected_component` stage: it removes 2,537,130 raised-frame
points, or 58.5726% of otherwise valid triangulations. Dense stereo and
triangulation do **not** show a comparable raised/static loss. Plane fitting,
plane-relative cropping and xyzC compression remove zero additional points.

## 2. What the official WASS stage does

Runtime-commit `wass_stereo.cpp` calls
`compute_zgap_percentile(ZGAP_PERCENTILE)` and
then `cluster_biggest_connected_component` before plane fitting. The frozen
config leaves `ZGAP_PERCENTILE` at its documented default 99.

In official `PovMesh.cpp`, the threshold is the requested percentile of
absolute Z differences between valid neighbouring triangulated points. A graph
uses four-neighbour image adjacency only when the neighbour's absolute Z gap is
below that threshold. WASS retains only the largest graph component. Sources:

- [`wass_stereo.cpp`, runtime commit `6b82aeb`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp)
- [`PovMesh.cpp`, runtime commit `6b82aeb`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/PovMesh.cpp)

The static `graph_components.jpg` is almost one component. The raised image is
split into several full-height vertical bands separated by invalid/Z-gap
boundaries; WASS retains one 1.794-million-point band group. The exact numeric
99th-percentile Z-gap is not printed and the pre-component full mesh was not
saved. Runtime-source review confirms that `SAVE_FULL_MESH` executes after
component extraction, while true pre-component exports are commented/compiled
out. Severing depth values remain `OBSERVABILITY_LIMITATION`; stage and count
loss are confirmed.

Speckle, uniqueness, disparity-range and morphology operate before
triangulation. Their individual rejection counts are not logged, but the final
triangulated count is slightly higher for the raised frames. They therefore
cannot account for the later 2.537-million-point difference. The configured
plane thresholds also cannot account for it because all component points
survive both plane crops.

## 3. Synthetic-image and theoretical-FOV checks

The candidate nominal focal length is `f=2318.84058 px`, baseline `B=0.20 m`.
For a parallel rig at camera-to-plane depth `Z`, disparity and horizontal
common field are

\[
d=fB/Z,\qquad W_{common}=N_xZ/f-B,
\]

where `N_x=2448 px`. Relative horizontal sensor overlap is `1-d/N_x`.

| quantity | static, Z=2.00 m | raised, Z=1.99 m | change |
|---|---:|---:|---:|
| truth disparity | 231.8841 px | 233.0493 px | +1.1652 px |
| sensor FOV width | 2.111400 m | 2.100843 m | -0.010557 m |
| sensor FOV height | 1.766400 m | 1.757568 m | -0.008832 m |
| common FOV width | 1.911400 m | 1.900843 m | -0.010557 m |
| horizontal overlap ratio | 90.5276% | 90.4800% | -0.0476 percentage points |
| truth samples visible in both cameras | 100% | 100% | 0 |
| rendered nonzero ratio per image | 77.4552% | 78.2819% | +0.8267 percentage points |

The 10 mm shift produces only the predicted 1.165 px disparity increase and a
0.0476-point common-FOV decrease. All truth samples remain jointly visible;
rendered and triangulated coverage both increase slightly. There is no 50%
loss in image texture, common visibility, disparity validity or triangulation.
Thus ordinary pinhole FOV and gross synthetic-image support are excluded as the
cause of the support collapse.

The vertical-band fragmentation appears only after triangulated neighbouring
depths are subjected to WASS's adaptive Z-gap graph. Whether point-sampled
rasterization and subpixel disparity interact with that graph threshold is a
remaining mechanism-level TODO because the rejected full mesh was not saved.
This uncertainty does not change the identified loss stage.

## 4. Raw observation support mask and physical valid domain

`grid_finite_mask` and physical observation support are different:

- `grid_finite_mask`: DCT 0.11.4 returns a full-one mask and finite values over
  the full rectangle, including extrapolated cells.
- `raw_observation_support_mask(t,y,x)`: true iff at least one final WASS xyzC
  point for frame `t`, after the shared official transform and scale, is
  assigned to that exact official grid cell. It changes no Z value and performs
  no interpolation.

For `H(t)=Z(t)-Z0`, the physically observed mask is

\[
M_H(t,y,x)=M_{raw,dynamic}(t,y,x)\land
            \left(\bigvee_{s\in static}M_{raw,static}(s,y,x)\right).
\]

This is the minimum traceable physical valid-domain definition under the
official gridder: both the dynamic value and at least one contributing static
reference observation must have raw WASS support. For a temporally fixed common
ROI, additionally intersect `M_H` across evaluated dynamic frames. The current
two raised masks are identical, so both definitions yield 51.4492%.

This mask is suitable for a **future pre-registered formal acceptance domain**
because it encodes observation provenance rather than DCT finiteness. It does
not retroactively replace this run's full-grid acceptance result. A minimum
point-count quality threshold beyond `>=1` is not introduced because it lacks a
pre-registered physical basis.

## 5. Full-grid and supported-domain metrics

Supported-domain values below are diagnostic only. No point is removed from
the stored grid and the original decision remains failed.

| metric | full DCT grid | raw-supported domain |
|---|---:|---:|
| evaluated coverage | 100% finite DCT | 51.4492% physically supported |
| signed bias | -1.1110 mm | -1.0829 mm |
| RMSE | 11.0795 mm | **1.2785 mm** |
| MAE | 5.6566 mm | **1.1163 mm** |
| maximum absolute error | 75.4659 mm | **6.6340 mm** |
| P50 absolute error | 1.5900 mm | 1.1043 mm |
| P90 absolute error | 17.2369 mm | 1.9045 mm |
| P95 absolute error | 25.6984 mm | 2.1387 mm |
| P99 absolute error | 47.2275 mm | 2.6690 mm |

This separation confirms that nonzero height recovery is internally consistent
where WASS supplies raw observations, while the official DCT finite domain is
not by itself a physical-validity domain.

## 6. Approximately 1 mm xyzC bias budget

The shared plane transform cannot remove or create a constant difference: its
common translation cancels, and its rotation is shared. Baseline multiplication
is the same exact configured `0.20 m` for all frames.

Using WASS's per-frame plane offsets before the shared mean-plane translation:

| quantity | static | raised |
|---|---:|---:|
| expected camera depth | 2.000000000 m | 1.990000000 m |
| WASS plane depth | 1.999379238 m | 1.990383236 m |
| absolute depth error | -0.620762 mm | +0.383236 mm |
| expected disparity | 231.884058 px | 233.049304 px |
| depth-equivalent disparity | 231.956053 px | 233.004432 px |
| equivalent disparity error | +0.071995 px | -0.044872 px |

Their differential disparity error is `-0.116867 px`, quantitatively sufficient
to explain the approximately `-1.00 mm` height bias through `Z=fB/d`.

Other bounded contributions are much smaller:

- using WASS's own plane offsets gives 8.996002 mm while the independent xyzC
  fit gives 8.998655 mm: plane-fit/decoded-cloud difference is only 0.002653 mm;
- xyzC header quantization gives conservative half-step Euclidean bounds of
  0.0194 mm (static) and 0.0146 mm (raised), far below 1 mm;
- a uniform baseline-scale error would affect both absolute depths in the same
  direction, whereas measured errors are -0.621 and +0.383 mm.

The 1 mm term is therefore classified as a **systematic differential WASS
reconstruction/autocalibration disparity bias**, not xyzC quantization, plane
subtraction, or configured baseline multiplication. Attribution within dense
matching versus recovered extrinsics remains UNKNOWN without an independent
pre-autocalibration disparity/depth export.

## 7. Root-cause classification and next action

At pipeline-effect level, WASS removal and gridder extrapolation are both
proven. At the stricter mechanism gate (synthetic local disparity bands versus
near-field Z-gap mismatch versus both), classification is **D: current
observation capability is insufficient**:

1. **WASS filtering effect:** the adaptive Z-gap largest-connected-component
   stage discards 58.57% of raised triangulated points. This creates the raw
   support deficit. Gross synthetic coverage and normal FOV are excluded.
2. **Gridder policy effect:** DCT 0.11.4 fills cells without observations and marks
   the whole domain finite. This converts the support deficit into 11.08 mm RMSE
   and 75.47 mm maximum error.
3. A smaller WASS reconstruction/autocalibration term produces about 1 mm mean
   bias even inside the supported domain.

The project interface now preserves raw observation support beside
`grid_finite_mask`, with formal semantics in
[`measurement_valid_domain.md`](../data_model/measurement_valid_domain.md).
Remain in Case 1 and seek an upstream-supported float pre-component output to
resolve A/B/C; the current release provides none.

No WASS parameter should be tuned yet. In particular, changing
`ZGAP_PERCENTILE`, matcher/stereo thresholds, DCT settings, or ROI before
capturing the rejected depth structure would erase the evidence being sought.
