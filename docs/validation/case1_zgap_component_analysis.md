# Case 1 Z-gap component-fragmentation analysis

Run date: 2026-08-12  
Runtime: WASS `1.11_heads/master-0-g6b82aeb`  
Status: **RULE AND FRAGMENTATION CONFIRMED; PRE-CLUSTER DEPTH OBSERVABILITY LIMITED**

No WASS parameter or source was changed. No Case 2 work was performed.

## 1. Exact runtime algorithm

Let the triangulated image-domain point at pixel `p=(u,v)` be
`X_p=(X_p,Y_p,Z_p)` in WASS camera coordinates. Invalid triangulations are not
vertices. Runtime source `PovMesh.cpp` builds a Z-gap sample list from each
valid `(u,v)`, `v>=1`, `1<=u<width-1`, to valid points at
`(u-1,v-1)`, `(u,v-1)`, and `(u+1,v-1)`:

\[
G=\{|Z_p-Z_q|:q\in\{upper\!\ left,upper,upper\!\ right\},p,q\ valid\}.
\]

It sorts `G` ascending and sets, for `r=ZGAP_PERCENTILE`,

\[
\tau=G_{\lfloor(r/100)|G|\rfloor}
\]

using zero-based indexing. The frozen default is `r=99.0`. `Z` and therefore
`tau` are in WASS camera-depth units (baseline-normalized before the later
gridder baseline multiplication).

A second graph has the valid pixels as vertices and only four-neighbour
left/right/top/bottom candidates. Edge `(p,q)` exists iff

\[
|Z_p-Z_q|<\tau.
\]

Notice the strict `<`: a gap equal to `tau` is disconnected. Depth-first graph
traversal labels components; the component with greatest vertex count is kept,
all others are invalidated. Ties keep the first encountered larger component
because the update condition is strict `>`.

Pseudocode matching runtime commit `6b82aeb`:

```text
gaps = sort(abs(Z[p] - Z[q]) for valid upper-left/upper/upper-right pairs)
tau = gaps[floor(ZGAP_PERCENTILE / 100 * len(gaps))]

for each unvisited valid pixel p in scan order:
    DFS using four-neighbours q where abs(Z[p]-Z[q]) < tau
    record component size
keep the largest component; invalidate every other component
```

Sources: [`PovMesh.cpp`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/PovMesh.cpp),
[`wass_stereo.cpp`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp).

## 2. Exact-count evidence

| stage | Static | Case 1 |
|---|---:|---:|
| valid triangulated vertices | 4,322,503 | 4,331,598 |
| retained largest component | 4,311,954 | 1,794,468 |
| removed by component stage | 10,549 (0.2440%) | 2,537,130 (58.5726%) |
| plane crops after component stage | 0 additional loss | 0 additional loss |

Thus component extraction, not disparity validity, triangulation or plane
cropping, creates the Case 1 support collapse.

## 3. Z-gap statistics and observability limitation

The requested pre-cluster `G` arrays were not preserved by this run. Runtime
logs print only “computing 99th percentile”, not `tau`. The release build has no
CLI/config output for `G`, `tau`, labels or all component sizes:

- `mesh_post_stereo.ply` and triangulated before/after exports are commented or
  compiled out in runtime source;
- `SAVE_FULL_MESH` is executed **after** largest-component extraction, despite
  its broad description, so it cannot recover rejected points;
- `disparity_final_scaled.png` is a rendered PNG, not the float disparity or
  camera-Z array;
- `graph_components.jpg` is lossy diagnostic colour output, not exact labels.

Therefore exact Static/Case 1 Z-gap minimum, median, P90, P95, P99, maximum,
numeric `tau`, total component count and full size distribution are
**UNKNOWN — OBSERVABILITY_LIMITATION**. Estimating them from PNG/JPEG would not
meet the requested mathematical traceability and is deliberately not done.

What is confirmed is that each frame computes its own 99th-percentile threshold
from its own triangulated depth field, so the Static and Case 1 thresholds need
not be equal even with unchanged configuration.

## 4. Spatial fragmentation supported by diagnostics

The runtime component JPEG is half-resolution (`1024 x 1224`) and supports only
qualitative geometry plus robust column statistics:

- Static: retained-component green covers about 85.89% of the diagnostic image;
  excluding the outer invalid margin, no internal column is more than 80% black.
- Case 1: green covers about 60.02%. Internal more-than-80%-black vertical runs
  occur at half-resolution columns 593--613, 731--747 and 865--885; a broad
  right-side invalid/removed interval begins near column 1002.
- The component display also contains multiple non-green component-colour bands
  on the left. Because JPEG colours are not exact labels, they prove multiple
  vertically extended regions but not the exact component count.

The fracture morphology is therefore **vertical banded**, not random isolated
speckle and not solely an outer boundary effect. Mapping through the rectified
image domain makes the bands image-coordinate vertical; final xyzC/grid support
shows corresponding missing x regions in plane coordinates. Exact boundary
coordinates in 3-D are unavailable without the rejected points.

## 5. Relation to synthetic imaging and disparity

Gross support remains normal:

| diagnostic | Static | Case 1 |
|---|---:|---:|
| rendered nonzero pixels | 77.4552% | 78.2819% |
| final disparity PNG zero ratio | 10.7601% | 10.4491% |
| triangulated ratio | 86.2172% | 86.3986% |
| truth disparity | 231.8841 px | 233.0493 px |
| horizontal common FOV | 90.5276% | 90.4800% |

The Case 1 final disparity PNG has only the same outer full-height zero run as
Static, not the component image's internal vertical breaks. Synthetic-image
column support improves slightly (fully invalid columns decrease from 358 to
347). Mean absolute texture gradients are nearly unchanged and slightly larger
in Case 1: horizontal `24.944 -> 25.076` and vertical `24.996 -> 25.127` gray
levels per pixel; P95 is `137 -> 138` in both directions.

These data exclude global texture loss, ordinary common-FOV change and invalid
dense disparity coverage as explanations. They do **not** distinguish whether
subpixel point-sampled rasterization produces locally quantized depth bands, or
whether WASS's per-frame 99th-percentile Z-gap graph is intrinsically sensitive
to the near-field plane. That requires the missing float pre-cluster depth.

## 6. Decision gate

The required mechanism classification is **D — current observation capability
is insufficient to decide A/B/C**.

- A pure synthetic-support failure is contradicted by coverage and disparity
  validity, but a local subpixel rasterization interaction is not excluded.
- A default Z-gap/near-field mismatch is plausible and the exact loss occurs in
  that WASS stage, but cannot be proven without `G` and `tau`.
- Consequently joint action C also cannot be established quantitatively.

The next phase must remain Case 1 and improve **observability**, not tune for a
pass. Use an upstream-supported build/output if one becomes available that
exports float pre-cluster points/depth, Z-gap threshold and component labels.
The current runtime offers no such official switch; record this limitation and
do not patch core WASS. `ZGAP_PERCENTILE`, matcher, stereo and gridder parameters
remain frozen.

## 7. Related measurement-domain result

Regardless of unresolved fracture mechanism, final xyzC observation provenance
is known. The formal mask layers and dual reporting protocol are specified in
[`measurement_valid_domain.md`](../data_model/measurement_valid_domain.md).
This does not retroactively change Case 1 acceptance.

## 8. One-millimetre bias budget

The independent xyzC plane difference is 8.998655 mm for 10.000000 mm truth.
The following budget separates bounded effects from unresolved reconstruction
terms; magnitudes are not summed as independent random errors.

| source | estimated magnitude | evidence | status |
|---|---:|---|---|
| disparity/reconstruction differential | equivalent `-0.116867 px`; height bias about `-1.001 mm` | depths implied by fitted Static/raised planes and `Z=fB/d` | leading combined term; dense matching share UNKNOWN |
| autocalibration/extrinsics | included in the same approximately 1 mm differential | all frames share one autocalibration; no independent fixed-extrinsic reconstruction exists | UNKNOWN contribution |
| baseline scaling | no separately observed differential; common factor `0.20 m` | identical explicit multiplier for all frames; absolute depth errors have opposite signs | not supported as main term |
| xyzC quantization | conservative half-step bounds `0.0194/0.0146 mm` | decoded xyzC header quantization ranges | proven negligible versus 1 mm |
| independent plane fitting | `0.002653 mm` difference from WASS plane-offset result | 8.998655 versus 8.996002 mm | proven negligible |
| gridder | mean changes by about `-0.110 mm`; creates large spatial tail outside support | xyzC mean difference versus grid mean and supported/full metrics | not source of original xyzC bias |
| static-reference subtraction | floating arithmetic only; no transform/interpolation | explicit common-grid subtraction using Static frames only | not supported as main term |

The approximately 1 mm xyzC bias is therefore retained as a systematic
**reconstruction/autocalibration differential**. Existing outputs cannot split
those two contributors, so neither is individually declared causal.
