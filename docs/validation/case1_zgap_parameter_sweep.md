# Case 1 ZGAP_PERCENTILE controlled sweep

Run date: 2026-08-12
Status: **CLASSIFICATION A; CASE 1 BASELINE RESULT REMAINS FAILED; CASE 2 NOT STARTED**

## 1. Purpose and permission boundary

Earlier diagnostics located the decisive support loss at WASS's
`cluster_biggest_connected_component` stage: the raised frames retained only
41.4274% of valid triangulations at the default `ZGAP_PERCENTILE=99`. Upstream
pre-cluster depth and the numerical threshold remain unavailable, so the
`OBSERVABILITY_LIMITATION` is preserved. This controlled experiment does not
claim to resolve that internal mechanism. It tests whether the one documented
control parameter changes support in the predicted direction without degrading
the accuracy of cells backed by raw WASS observations.

Only `ZGAP_PERCENTILE` changed. WASS and wassgridsurface source, acceptance
limits, images, intrinsics, extrinsics, baseline, working distance, matcher
results, autocalibration results, all other stereo settings, DCT settings, grid
extent and spacing were held fixed. No ROI reduction, outlier deletion,
smoothing, filtering or alternate interpolation was introduced.

## 2. Source rule and parameter type

At runtime commit `6b82aeb`, `wass_stereo.cpp` declares the setting with
`INCFG_REQUIRE(double, ZGAP_PERCENTILE, 99.0, ...)`. Decimal values are therefore
supported and both 99.5 and 99.9 were accepted by the real executable.
`PovMesh.cpp` sorts the valid four-neighbour absolute camera-Z differences
`G` and selects

\[
\tau=G[\lfloor(r/100)|G|\rfloor],
\]

where `r` is `ZGAP_PERCENTILE` and `0 <= r < 100`. Increasing `r` cannot lower
the selected order statistic. It may connect more observations, but can also
admit erroneous depth transitions; support and accuracy must therefore be
evaluated together. Exact `tau` is still not emitted by the official runtime.

Sources: local `D:/wass/src/wass_stereo/wass_stereo.cpp` and
`D:/wass/src/wass_stereo/PovMesh.cpp`, both at the bound runtime commit; see
[`case1_zgap_component_analysis.md`](case1_zgap_component_analysis.md).

## 3. Frozen inputs and execution

The four original frames were reused in place: two static frames followed by
two `+0.010 m` raised frames. No image was regenerated. Candidate-camera
simulation values remained 2448 x 2048 px, 3.45 um pixels, nominal 8 mm lens,
baseline 0.20 m and working distance 2.00 m. Baseline and distance remain
`SIMULATION_TEST_PARAMETER`, not hardware parameters.

The left/right SHA-256 hashes occur in identical stereo pairs:

| frame | left/right SHA-256 |
|---|---|
| 000000 | `5700D4CE03602E993AD7517B74C67CBA7BE677DD9523E971AB1AD38BEB82D877` |
| 000001 | `7127EAA0857F8216BB317BFBC859630A7F8C26EF18BE4FC5653A13A7F481F78A` |
| 000002 | `147305A39455A511AD6E394D06A48331E2CA85B0202B479C820D3FF3A16E3CE1` |
| 000003 | `D3708E9FEDAD64AC12C96D9295F0EE1A9FFCB0E744A3F487C667AB28BA9DE9EB` |

The scan values were `95, 97, 98, 99, 99.5, 99.9`. Existing prepare, match and
autocalibrate products were copied into isolated, outside-Git workspaces because
the changed parameter is first consumed by `wass_stereo`. For every value, all
four frames then ran through official `wass_stereo`, one new shared
`planes.txt`, official `wassgridsurface 0.11.4` setup and DCT grid, strict
`StandardizedGrid3D` parsing, static-only `Z0`, and `H=Z-Z0`. Every executable
returned zero. Large artifacts remain outside Git under
`D:/stereo-wave-height-runs/case1-zgap-sweep-20260812`.

The valid triangulation counts were invariant: 4,322,503 per static frame and
4,331,598 per raised frame. This confirms that the scan did not change dense
matching or triangulation.

## 4. Support results

Counts are per frame; each identical frame pair produced identical counts.
Retained ratio is largest component divided by valid triangulations. Raw
support is the dynamic/static intersection defined in
[`measurement_valid_domain.md`](../data_model/measurement_valid_domain.md).

| r | static largest component | static retained | raised largest component | raised retained | raw supported grid |
|---:|---:|---:|---:|---:|---:|
| 95 | 4,044,155 | 93.5605% | 1,794,468 | 41.4274% | 51.4023% |
| 97 | 4,196,139 | 97.0766% | 1,794,468 | 41.4274% | 51.4375% |
| 98 | 4,274,666 | 98.8933% | 1,794,468 | 41.4274% | 51.4492% |
| 99 | 4,311,954 | 99.7560% | 1,794,468 | 41.4274% | 51.4492% |
| 99.5 | 4,321,866 | 99.9853% | 4,326,851 | 99.8904% | 100.0000% |
| 99.9 | 4,321,873 | 99.9854% | 4,331,590 | 99.9998% | 100.0000% |

The raised sequence has a sharp connectivity transition between 99 and 99.5;
there is no gradual raised-support response from 95 through 99.

## 5. Accuracy results

All errors are relative to `H_true=+0.010 m`. Supported-domain metrics retain
their diagnostic status; the historical full-grid acceptance result is not
replaced.

| r | supported mean H (mm) | bias (mm) | supported RMSE (mm) | MAE (mm) | max (mm) | full-grid RMSE (mm) | full-grid MAE (mm) | full-grid max (mm) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 95 | 8.8476 | -1.1524 | 1.3208 | 1.1886 | 6.6795 | 14.4120 | 7.4569 | 95.0706 |
| 97 | 8.8843 | -1.1157 | 1.3772 | 1.1834 | 14.3044 | 34.3133 | 17.6720 | 231.8712 |
| 98 | 8.9095 | -1.0905 | 1.2696 | 1.1265 | 5.2353 | 8.5015 | 4.5596 | 73.4457 |
| 99 | 8.9186 | -1.0814 | 1.2491 | 1.1007 | 6.5992 | 19.9817 | 8.4974 | 167.9172 |
| 99.5 | 9.1073 | -0.8927 | 1.0266 | 0.9158 | 1.6413 | 1.0266 | 0.9158 | 1.6413 |
| 99.9 | 9.1061 | -0.8939 | 1.0269 | 0.9162 | 1.6454 | 1.0269 | 0.9162 | 1.6454 |

Finite-grid coverage was 100% and hole rate 0% for every DCT result. At 99.5
and 99.9 raw support also covers every grid cell, so full-grid and supported
metrics coincide.

The new r=99 DCT result (19.982 mm RMSE) differs from the frozen original r=99
result (11.080 mm) despite identical inputs and nominal DCT configuration. The
official DCT optimization is therefore not demonstrated run-deterministic in
this experiment. This prevents interpreting the non-monotonic 95--99 full-grid
numbers as a precise parameter curve. It does not affect the exact WASS point
counts or the observed 99-to-99.5 support transition.

## 6. Point-cloud quality

The recovered offset is the raised-minus-static orthogonal-plane Z intercept
after the shared plane transform and 0.20 m scale. Residuals are per frame and
the two frames in each class are identical.

| r | recovered offset (mm) | static residual RMSE / max (mm) | raised residual RMSE / max (mm) |
|---:|---:|---:|---:|
| 95 | 8.8893 | 0.5164 / 1.4298 | <0.000001 / <0.000001 |
| 97 | 8.9410 | 0.5973 / 1.8594 | <0.000001 / <0.000001 |
| 98 | 8.9792 | 0.6392 / 1.8305 | <0.000001 / <0.000001 |
| 99 | 8.9987 | 0.6705 / 2.3600 | <0.000001 / <0.000001 |
| 99.5 | 9.2409 | 0.6783 / 5.0611 | 0.5900 / 7.1903 |
| 99.9 | 9.2399 | 0.6783 / 5.0611 | 0.5904 / 7.1934 |

Including almost all raised observations increases its plane residual from the
artificially near-zero retained band at r<=99 to 0.590 mm, but the supported
height RMSE improves to about 1.027 mm rather than degrading. The recovered
offset bias also improves from about -1.001 mm at r=99 to -0.759 mm at r=99.5.

## 7. Trade-off and decision

The result is **classification A**:

- raising r from 99 to 99.5 changes raised retention from 41.4274% to 99.8904%
  and raw grid support from 51.4492% to 100%;
- supported-domain RMSE improves from 1.249 mm in this controlled rerun to
  1.027 mm, rather than worsening;
- r=99.9 adds only 0.1094 percentage points of raised retention and changes
  supported RMSE by less than 0.001 mm.

There is therefore a real, interpretable trade-off interval and evidence that
the default 99 is mismatched to this frozen near-field synthetic geometry.
Among tested values, **99.5 is the lowest value beyond the observed transition**
and is the supported candidate for the formal Case 1 adapted configuration;
this is not an unconstrained optimum search and is not a hardware/default WASS
recommendation. Before changing the canonical Case 1 configuration, repeatability
of the official DCT output should be registered and checked. Acceptance limits
remain unchanged, the original default-99 Case 1 remains failed, and Case 2
remains prohibited.

## 8. Remaining limitations

- Official pre-cluster float depth, actual `tau`, and component labels remain
  unavailable: `OBSERVABILITY_LIMITATION` is not lifted.
- The precise cause of the 99-to-99.5 component merge remains unobserved.
- DCT run-to-run variability needs a controlled repeatability study; no DCT
  parameter was changed here.
- Results apply only to the frozen ideal synthetic Case 1 and do not establish
  real-camera or real-water centimetre accuracy.
- No Case 2 data was generated or processed.
