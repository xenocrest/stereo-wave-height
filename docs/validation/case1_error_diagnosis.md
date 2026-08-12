# Case 1 height-error diagnosis

Run date: 2026-08-11  
Status: **DIAGNOSIS COMPLETE; CASE 1 REMAINS FAILED; CASE 2 NOT STARTED**

The follow-up stage trace is documented in
[`case1_support_trace.md`](case1_support_trace.md). It locates the upstream
loss at WASS's Z-gap largest-connected-component extraction and defines the
raw-observation physical domain without changing this run's formal decision.
The mechanism-level follow-up is
[`case1_zgap_component_analysis.md`](case1_zgap_component_analysis.md); its
decision is `D — OBSERVABILITY_LIMITATION`, not an unsupported A/B/C choice.

This is a read-only decomposition of the frozen Case 1 run. No WASS or
`wassgridsurface` source, parameter, interpolation method, mask, acceptance
gate, or evaluation region was changed. Machine-readable values are in
[`case1_error_diagnosis_metrics.json`](case1_error_diagnosis_metrics.json).

## 1. Failure and diagnostic layers

For `H_true=+0.010 m`, the formal grid result was `H_mean=0.00888897 m`, bias
`-0.00111103 m`, RMSE `0.01107954 m`, MAE `0.00565656 m`, maximum absolute
error `0.07546593 m`, and standard deviation `0.01102369 m`. RMSE and maximum
error failed their frozen gates. The diagnosis keeps these stages separate:

```text
synthetic truth -> WASS xyzC -> common scale/plane transform
                -> raw grid support -> DCT grid -> Z0 subtraction
```

## 2. Synthetic truth

The stored `height_fields.npz` was compared directly. Across all `801 x 901`
cells, `H_case1-H_static` has minimum and maximum `0.010000000000000000 m`,
mean `0.009999999999999998 m`, and standard deviation `1.735e-18 m`. It is
element-for-element equal to the generated float64 constant `0.010`. Synthetic
truth is excluded as the source of the observed spatial error.

## 3. xyzC plane-level result before gridding

Point indices were **not** paired. Each decoded `mesh_cam.xyzC` was transformed
with the same four-frame mean plane and explicit `0.20 m` baseline scale. An
orthogonal least-squares plane `n dot X + c=0` was fitted independently. Normals
have positive Z; plane position is `Z(X=0,Y=0)=-c/n_z`.

| frame | type | points | fitted normal `(nx,ny,nz)` | Z at origin (m) | residual RMSE (m) | residual max (m) |
|---|---|---:|---|---:|---:|---:|
| 000000 | static | 4,311,954 | `(5.366e-7,1.259e-4,0.999999992)` | -0.004500654 | 0.000670463 | 0.002359973 |
| 000001 | static | 4,311,954 | same (identical hash) | -0.004500654 | 0.000670463 | 0.002359973 |
| 000002 | raised | 1,794,468 | `(-2.171e-5,4.643e-5,0.999999999)` | +0.004498001 | `2.654e-12` | `9.329e-12` |
| 000003 | raised | 1,794,468 | same (identical hash) | +0.004498001 | `2.654e-12` | `9.329e-12` |

Therefore `Delta H_xyzC=0.008998655 m`, with scalar error
`-0.001001345 m`. WASS contributes about 1.00 mm of mean-height bias, but this
is an order of magnitude below the post-grid RMSE and 75.5 mm maximum. The
raised xyzC surface is planar at decoded precision; large spatial excursions
are absent before gridding.

## 4. Raw point support on the official grid

This statistic only counts transformed xyzC points assigned to the nearest
official `160 x 160`, `0.01 m` cell. It estimates no Z and is not an alternative
interpolator.

| type | total points | inside grid | supported cells | unsupported cells | support ratio |
|---|---:|---:|---:|---:|---:|
| static | 4,311,954 | 3,439,690 | 25,600 | 0 | 1.000000 |
| raised | 1,794,468 | 1,697,433 | 13,171 | 12,429 | 0.514492 |

Raised-frame counts over all cells have P50/P90/P95/P99 of
`43/144/144/144`; only 21 cells contain 1--4 points. The pattern is mainly a
supported/unsupported split. Official finite-output coverage `1.0` therefore
hides 48.55% of raised cells with no raw xyzC support.

## 5. Spatial error distribution

Formal error remains `e=H_calc-0.010 m` on the unchanged full grid. The
diagnostic boundary is the outer 16 cells (10% of width); it does not alter
acceptance.

| statistic | result (m) |
|---|---:|
| median signed error | -0.001126671 |
| P50 absolute error | 0.001590024 |
| P90 absolute error | 0.017236876 |
| P95 absolute error | 0.025698418 |
| P99 absolute error | 0.047227534 |
| center RMSE | 0.006234619 |
| boundary RMSE | 0.016488975 |

The maximum is `-0.075465926 m` at frame 000002 and physical coordinate
`(x,y)=(+0.695,+0.085) m`. It is on the final x boundary and has zero raised
xyzC support.

For frame 000002, supported-cell RMSE is `0.001271122 m`, unsupported-cell RMSE
is `0.019815272 m`, and unsupported cells contribute 99.57% of squared error.
For frame 000003 these are `0.001285912 m`, `0.010467667 m`, and 98.43%.
Correlation between `log(1+point count)` and absolute error is `-0.496/-0.570`.
Every top-5% and top-1% error cell is unsupported. For frame 000002, 93.28% of
the top 5% and 100% of the top 1% are also in the boundary ring. The long tail
is therefore localized to DCT values without raised-frame raw support,
especially near the boundary.

## 6. DCT behavior confirmed from 0.11.4 source

The installed locked source is under
`D:/stereo-wave-height-runs/wassgridsurface-0.11.4-venv/Lib/site-packages/wassgridsurface/`.
`wassgridsurface.py` quantizes raw points, writes median Z into sparse `ZZ`, and
passes NaNs to `DCTInterpolator.py`. The latter:

1. builds `orig_pts_mask = 1-isnan(I)`;
2. multiplies data loss by this mask, so unsupported cells do not constrain it;
3. reconstructs the entire rectangle with a truncated DCT coefficient field;
4. returns `Irec, ones_like(mask)`.

Full-domain completion/extrapolation and the full-one output mask are thus
confirmed by source, not visual judgement. Both raised frames also reached the
500-iteration maximum and sparse `ZZ` aggregation emitted an all-NaN-slice
warning. A specific “DCT ringing” mechanism is **not separately proven**; the
supported term is “sparse-support full-domain DCT artifact.”

## 7. Common reference and coordinates

- All frames use one `planes.txt` mean, `0.20 m` scale, `config.mat`, x/y grid,
  coordinate label and NetCDF product.
- Parsed order is explicitly `[time,y,x]`; x maps to columns and y to rows.
- x/y spacing is exactly `0.01 m`; parser and tests reject mismatched grids.
- Z0 uses only static frames 000000--000001.
- xyzC and grid mean differences both have the requested positive sign.

This excludes separate transforms, scale mismatch, transpose, x/y swap, sign
inversion, dynamic leakage into Z0, and half-cell origin shifts as explanations
for the 75 mm excursion. Height subtraction adds no interpolation or correction.

## 8. Before/after comparison and judgement

| layer | recovered height | error |
|---|---:|---:|
| exact truth | 0.010000000 m | approximately 0 |
| WASS xyzC fitted planes | 0.008998655 m | -0.001001345 m scalar bias |
| official DCT grid | mean 0.008888970 m | RMSE 0.011079538 m; max 0.075465926 m |

Two effects are proven. WASS/scale contributes roughly 1 mm mean bias. The
acceptance failure's large spatial tail appears after xyzC: supported grid cells
retain about 1.28 mm RMSE, while unsupported DCT cells contain more than 98% of
squared error and every top-tail cell. The **primary cause of the RMSE and
maximum-error failure is official DCT full-domain reconstruction over missing
raised-frame raw support**. WASS retains only 1.79 million raised points because
its post-triangulation Z-gap largest-connected-component stage removes 2.537
million raised points. The precise disparity/depth mechanism that creates the
vertical component boundaries remains UNKNOWN because the rejected full mesh
was not saved.

## 9. Next work

1. Stay in Case 1 and capture the rejected pre-component depth structure with
   an official diagnostic output before changing any threshold.
2. Review the official gridder's intended validity/ROI policy and define a raw
   support quality product separately from finite DCT output. Do not
   retroactively remove cells or claim this run passes.
3. Pre-register any controlled Case 1 rerun or official-tool configuration
   experiment; hold truth, baseline, working distance and gates fixed.
4. Do not start Case 2 until non-zero Case 1 passes the original gates.

No filter, smoother, custom interpolator, parameter tuning, ROI shrink, outlier
deletion, or acceptance-gate change was performed or proposed as a shortcut.
