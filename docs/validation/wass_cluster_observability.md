# WASS cluster observability audit for Case 1

> Follow-up status: **DIAGNOSTIC_BUILD_NOT_NUMERICALLY_EQUIVALENT**. An isolated read-only diagnostic patch was built, but frozen Case 0 and Case 1 `mesh_cam.xyzC` hashes differed from production. Its data are rejected; see [wass_diagnostic_build.md](wass_diagnostic_build.md).

Audit date: 2026-08-12

Runtime: WASS `1.11_heads/master-0-g6b82aeb`

Decision: **NO_OFFICIAL_OBSERVABILITY_INTERFACE**

## 1. Scope and outcome

The audit searched the local package `D:/wass`, runtime commit `6b82aeb`,
official GitHub master, tags v1.5--v1.11, relevant historical branches, commit
history, generated config, CLI usage and official documentation. It sought a
configuration option, command-line option, compile-time diagnostic, official
intermediate cache or companion reader that exposes all of:

1. float pre-cluster camera depth;
2. the numeric Z-gap threshold `tau`;
3. lossless component labels and complete component-size distribution.

None exists in the audited upstream code. The current limitation cannot be
removed using an official interface without changing source. Per project rule,
WASS was not patched, rebuilt or rerun.

## 2. Exact pipeline and data structures

Runtime `wass_stereo.cpp` executes:

```text
sgbm_dense_stereo(Environment::disparity: cv::Mat)
  -> triangulate(Environment)
  -> Environment::mesh: std::unique_ptr<PovMesh>
  -> PovMesh::compute_zgap_percentile(99.0)
  -> PovMesh::cluster_biggest_connected_component(workdir, tau)
  -> ransac_find_plane / crop_plane / refine_plane / crop_plane
  -> mesh_cam.xyzC
```

The relevant runtime structures are:

| object | source | type / shape | invalid representation |
|---|---|---|---|
| dense disparity | `Environment::disparity` in `wass_stereo.cpp` | OpenCV `cv::Mat`; cleaned disparity is `CV_32FC1` | zero in the cleaned disparity path |
| pre-cluster 3-D lattice | `Environment::mesh`, implementation `PovMeshImpl::data` | row-major `std::vector<PovMesh::Point>`, length `width*height`; indexed `data[v*width+u]` | `Point.valid == false` |
| 3-D point | `PovMesh::Point::p3d` | `cv::Vec3d` (`double X,Y,Z`) | point ignored when `valid=false` |
| traversal state | `visited`, `component_id` | `bool`, `int`; initialized false / -1 | not a physical invalid marker |

`triangulate` computes `cv::Vec3d p3d`, then calls
`mesh->set_point(image_u,image_v,p3d,...)`. Consequently the requested
pre-cluster depth is exactly `PovMeshImpl::PTc(u,v).p3d[2]` for valid points,
on the rectified right-image lattice used by the mesh. It is not a separate
persisted depth-buffer variable.

The coordinates inherit the scale of the stereo translation `T`. In this run
they are baseline-normalized camera coordinates; `wassgridsurface` later
multiplies by the explicit `0.20 m` baseline. Thus Z-gap and `tau` share the same
baseline-normalized camera-Z unit.

Sources:

- [`wass_stereo.cpp` at `6b82aeb`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp)
- [`PovMesh.h` at `6b82aeb`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/PovMesh.h)
- [`PovMesh.cpp` at `6b82aeb`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/PovMesh.cpp)

## 3. Exact threshold and connectivity implementation

For current valid point `(j,i)`, loops use `i=1..height-1` and
`j=1..width-2`. Z-gap samples include each valid upper-left, upper and
upper-right neighbour:

```text
abs(Z[j,i] - Z[j-1,i-1]) if both valid
abs(Z[j,i] - Z[j  ,i-1]) if both valid
abs(Z[j,i] - Z[j+1,i-1]) if both valid
```

Invalid current or neighbour points are skipped. After ascending sort:

```text
index = floor(percentile / 100.0 * gaps.size())
tau = gaps[index]
```

`r=99.0` comes from `INCFG_REQUIRE(double, ZGAP_PERCENTILE, 99.0, ...)`; the
frozen Case 1 config does not override it, so the generated per-workdir config
records the default. The cast through `floor` produces a truncated zero-based
index.

The component graph then uses four-neighbour left/right/top/bottom adjacency,
not the three-neighbour sampling pattern above. An edge is admitted only when
both points are valid, the neighbour is unvisited, and
`abs(Zp-Zq) < tau`. Equality is disconnected. Depth-first traversal labels a
component, and strict `component_size > biggest_component_size` selects the
largest encountered component. `extract_component(biggest_id)` invalidates all
other points.

The implementation may stop enumerating once remaining unvisited nodes are
fewer than the current largest component. This is sufficient to prove the
largest component but means a complete small-component count/size distribution
is not guaranteed even in the transient `component_id` fields.

## 4. Audited official outputs and switches

| candidate | actual behaviour | satisfies request? |
|---|---|---|
| `SAVE_FULL_MESH=true` | writes `mesh_full.ply` **after** largest-component extraction and before plane filtering | no pre-cluster points |
| `SAVE_AS_PLY=true` | writes final, plane-filtered mesh | no |
| `disparity_stereo_ouput.png` / `disparity_final_scaled.png` | rendered PNG diagnostics, not lossless float disparity/depth | no |
| `graph_components.jpg` | official colour visualization; green is retained component, others outliers; resized 0.5 and JPEG-compressed | no lossless labels or size table |
| `mesh_post_stereo.ply` | source block is inside `/* debug ... */` comments across audited tags/branches | not a build option |
| `mesh_triang_before.ply` / `mesh_triang_after.ply` | calls are source-commented | not a build option |
| `DEBUG_CORRESPONDENCES`, other local macros | source constants for unrelated interactive/reprojection diagnostics | no cluster observability |
| Debug CMake/MSVC build | changes compiler build mode only; does not uncomment exports or add logging | no |
| `--measure`, `--rectify-only` | interactive two-point measurement / rectification only | no |
| logs | print percentile request and largest component id/size, but not numeric `tau` or all sizes | partial only |

Official documentation describes `graph_components.jpg` as connected components
with only green retained, and documents `ZGAP_PERCENTILE`, but provides no
binary label schema or pre-cluster reader. Local MATLAB loaders read final xyzC
only.

## 5. Historical-source result

The same inactive `mesh_post_stereo.ply` debug block and absence of threshold
logging/component-label files were confirmed in tags v1.5, v1.6, v1.7, v1.8,
v1.11, master and audited related branches. Commit history contains no exposed
runtime switch that enables it. A source edit to uncomment/add output could
preserve algorithm mathematics, but it would still be a WASS source patch and
is explicitly outside this task.

## 6. Consequence for Case 1

No new Static or Case 1 Z-gap statistics or exact component distributions are
reported. Existing PNG/JPEG files cannot reproduce double-precision camera Z,
numeric `tau`, or lossless labels. Re-triangulating project-side from rendered
disparity would create an unofficial parallel reconstruction path and is also
not accepted.

Therefore:

- Static Z-gap min/P50/P90/P95/P99/max and `tau`: **UNKNOWN**;
- Case 1 Z-gap min/P50/P90/P95/P99/max and `tau`: **UNKNOWN**;
- complete component count and top-10 sizes: **UNKNOWN**;
- A/B/C mechanism classification: remains **D — OBSERVABILITY_LIMITATION**.

## 7. Next action

Stop rather than patch WASS. The evidence-preserving next action is upstream
coordination: request an official diagnostic interface/version that exports a
lossless pre-cluster `PovMesh` depth/validity lattice, numeric `tau`, and full
label/size data. The request should also clarify whether complete enumeration
must disable the current safe early-termination optimization for diagnostics.

Only after an upstream-supported interface exists should Case 0/Case 1 be rerun
with every reconstruction parameter frozen. Case 2 remains prohibited.
