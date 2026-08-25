# HomeTank_004 WASS Performance Profile

## Scope

This is a read-only engineering profile of three fixed wave inputs. It does not change WASS, calibration, matching, triangulation, height results, or historical experiment conclusions.

`prepare` and `match` were rerun in isolated work directories with the same PNG inputs and unchanged commands. Stereo substage values come from WASS's own timing table in the already completed run. Output timing measures `mesh_cam.xyzC` decoding, baseline scale application, and ASCII XYZ/PLY writing. Therefore `total` is an explicitly documented component sum, not a single enclosing stopwatch measurement.

## Results

| Frame | Prepare (s) | Match (s) | Rectify + dense (s) | Triangulation (s) | Stereo postprocess (s) | Output (s) | Total (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 000000 | 0.140 | 11.241 | 4.097 | 0.333 | 12.946 | 0.386 | 29.204 |
| 000001 | 0.126 | 11.497 | 4.081 | 1.299 | 5.906 | 0.585 | 23.555 |
| 000002 | 0.137 | 11.904 | 4.129 | 0.353 | 6.082 | 0.508 | 23.174 |
| Mean | 0.134 | 11.547 | 4.103 | 0.662 | 8.311 | 0.493 | 25.311 |

Stereo postprocessing contains the runtime-reported Z-gap statistics, outlier removal, plane fitting, and plane refinement. Frame 000000 spent 10.736 s in outlier removal alone; this explains the maximum total and demonstrates data-dependent variance.

## Bottleneck conclusion

The largest repeatable stage is `match` at 11.547 s/frame. Stereo postprocessing is second at 8.311 s/frame on average and is the largest source of variation. Rectification plus dense stereo averages 4.103 s/frame; triangulation and output I/O are not the primary bottlenecks in this three-frame measurement. No real-time-performance claim is made.

Machine-readable evidence: [wass_performance_profile.json](wass_performance_profile.json).
