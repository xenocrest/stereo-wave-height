# Measurement valid-domain specification

Status: **PROJECT SPECIFICATION / PRE-REGISTRATION REQUIRED BEFORE FORMAL USE**
Units: masks are dimensionless booleans; grid coordinates are metres.

## 1. Purpose

`wassgridsurface 0.11.4` DCT output being finite does not prove that a grid cell
contains a stereo-derived 3-D observation. This project therefore preserves
three explicitly different mask layers. None changes, filters, interpolates or
smooths `Z` or `H`.

## 2. Raw observation layer

For WASS frame `t`, transform every **final real WASS xyzC point** with the same
official plane transform and physical baseline scale used by the gridder. Let
`C(t,y,x)` be the count assigned to the nearest cell of the already fixed
official x/y grid. Cell edges lie halfway between adjacent grid coordinates.

\[
M_{raw}(t,y,x)=[C(t,y,x)\ge 1].
\]

`raw_observation_support_mask` means only that at least one final WASS 3-D
observation supports the cell. It is not inferred from DCT output, images,
truth, neighbouring cells or interpolation. The `>=1` rule is the minimum
provenance rule; any future density threshold requires separate physical
pre-registration.

## 3. Grid reconstruction layer

\[
M_{grid}(t,y,x)=\operatorname{isfinite}(Z_{grid}(t,y,x))
\land M_{gridder}(t,y,x).
\]

This is named `grid_finite_mask` or `reconstructed_by_gridder`. With the locked
DCT 0.11.4 path, the interpolator returns a full-one mask and reconstructs the
whole rectangle, so `M_grid` may be true where `M_raw` is false. It describes a
numerical product, not direct physical observation support.

## 4. Height-reference support

For static frames `s` admitted to the independent static reference,

\[
M_0(y,x)=\bigvee_{s\in S_{static}}M_{raw}(s,y,x).
\]

This matches the current valid temporal mean: at least one raw-supported static
sample is required. If the reference method later requires a minimum count,
that rule must be versioned and pre-registered.

## 5. Validation-eligible layer

For dynamic frame `t`,

\[
M_{eligible}(t,y,x)=M_{raw}(t,y,x)\land M_0(y,x)
\land M_{grid}(t,y,x)\land M_{coord/quality}(t,y,x).
\]

`M_coord/quality` is true only when coordinate system, unit, common x/y grid,
scale, axis direction and any separately pre-registered quality rule are valid.
Unknown metadata must fail rather than default to true.

For a time-invariant common measurement footprint, use

\[
M_{common}(y,x)=\bigwedge_{t\in T_{evaluation}}M_{eligible}(t,y,x).
\]

The Case 1 dynamic masks are identical, so frame-wise and common footprints are
both 51.4492%.

## 6. Required reporting

Until a later protocol explicitly adopts the physical domain, every validation
must report both:

1. **Full reconstruction domain:** all `M_grid=true` cells, including gridder
   reconstruction/extrapolation.
2. **Raw-supported physical domain:** `M_eligible=true` cells, plus eligible
   coverage relative to the declared grid.

The second result does not retroactively replace the first or change an earlier
acceptance decision. Reports must state the grid, cell assignment rule, static
frames, dynamic frames, coordinate checks, supported count and coverage.

## 7. Case 1 instantiation

Static xyzC supports all 25,600 cells. Each raised frame supports 13,171 cells,
so `M_eligible` has 51.4492% coverage. Diagnostic supported-domain metrics are
RMSE 1.279 mm, MAE 1.116 mm and maximum error 6.634 mm, versus full-grid RMSE
11.080 mm and maximum error 75.466 mm. Case 1 remains formally failed because
this specification was established after the frozen full-grid decision.

## 8. Traceability

- Project implementation: `src/validation/diagnostics.py`
- WASS xyzC/grid mapping: `docs/wass/wassgridsurface_integration.md`
- Case 1 evidence: `docs/validation/case1_support_trace.md`
- DCT mask behavior: installed `wassgridsurface==0.11.4`

No WASS or gridder source modification is permitted by this specification.
