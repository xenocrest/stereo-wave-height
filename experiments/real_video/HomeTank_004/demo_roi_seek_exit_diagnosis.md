# HomeTank_004 demo ROI, seek, and exit diagnosis

## Scope

This diagnosis addresses three demo usability failures: the unexpectedly small reconstructed display area, non-functional random video seeking, and failure to exit after selecting delete-all. It audits the frozen GUI artifacts and does not rerun WASS or alter calibration, synchronization, MLS, dense-completion policy, or reconstruction parameters.

## Audited measurement

- GUI session: `%LOCALAPPDATA%/StereoWaveHeightDemo/gui_sessions/20260831-104155`
- Measurement: `measurement_18.784s/attempt_+0`
- Selected time: `18.783833 s`
- Canonical camera: cam1/right, `1920 x 1080 px`

The measurement request and dense result both used the historical polygon `[(700,340), (900,340), (900,520), (700,520)]`. Its inclusive raster mask contains 36,381 pixels and covers only about `1.75%` of the canonical image. Visual inspection confirms that the visible water region is substantially larger. The overlay is aligned with this polygon; no canvas-to-canonical or overlay-coordinate defect was found.

Dense-status counts inside the historical ROI were:

| Status | Pixels | Fraction |
|---|---:|---:|
| OBSERVED | 5,487 | 15.082% |
| ESTIMATED | 1 | 0.00275% |
| UNSUPPORTED | 30,893 | 84.915% |

The primary cause of the small display patch is therefore `SMALL_RESULT_AREA_CAUSED_BY_DEMO_ROI`. The ROI was also mostly unsupported, and enlarging it must not convert unsupported pixels into valid height.

## Reconstruction-quality evidence

The existing artifacts report 37 matcher correspondences with mean error `0.2924`, 209,437 valid triangulated points, 125,518 points in the largest component, and 125,454 final XYZ points. Despite this point count, the metric XYZ support spans only approximately `69.04 x 89.80 mm` laterally (`X`) and vertically (`Y`), with `Z` span `102.26 mm`. This is spatially limited support rather than simply a low raw point count.

The frozen calibration remains explicitly failed and unapproved:

- stereo RMS: `7.922425 px`
- epipolar RMS: `9.508413 px`
- vertical rectification RMS: `21.122547 px`
- calibrated baseline: `0.0686847116 m`
- `approved_for_wass: false`

All reconstructed heights span `18.093–126.308 mm`, with median `34.671 mm`; the water-mask subset spans `19.393–45.123 mm`, with median `34.614 mm`. The plane RMS is `3.621 mm`. The large offset relative to the static reference and the failed calibration gate mean the display is diagnostic, not a validated physical measurement. The result-quality classification is the combination `SPARSE_WASS_SUPPORT_CONFIRMED` (spatial support) and `CALIBRATION_QUALITY_LIMITATION_CONFIRMED`. No WASS tuning is justified by this usability task.

## ROI correction

The packaged and experiment templates no longer carry the historical fixed polygon. The GUI now requires the user to pause on the canonical right image, choose **设置水面区域**, and drag a rectangle. Canvas coordinates are explicitly transformed to canonical image pixels, the rectangle remains visible, and the user may select it again. The selected canonical-cam1 polygon is written into the per-measurement backend configuration. Solving is refused until an ROI is selected.

The ROI is only a query domain. `OBSERVED`, `ESTIMATED`, and `UNSUPPORTED` retain their original meaning, and unsupported pixels remain unsupported.

## Calibration warning

The GUI displays a prominent quality warning using the repository's existing `CalibrationQualityThresholds`. This adds no new threshold and does not block a diagnostic demonstration; it warns that poor calibration can make later 3D results unreliable.

## Exit failure and correction

The delete helper previously accepted only the hard-coded root `D:/stereo-wave-height-runs/gui_sessions`, whereas the packaged application creates sessions under `%LOCALAPPDATA%/StereoWaveHeightDemo/gui_sessions`. The safety check rejected the real current session before window destruction, which made delete-all appear unresponsive.

Each session now retains its resolved root. Deletion is permitted only when the target's direct parent is that exact root, so only the current session can be removed. Shutdown stops the decoder, cancels Tk callbacks, closes Matplotlib windows and NPZ handles, attempts cleanup, and always destroys the root. A Windows file-lock cleanup failure produces a warning with the residual directory but no longer prevents exit.

## Random seek correction

Timeline movement updates only the requested-time label. Releasing the slider submits one background OpenCV seek. A generation token invalidates stale requests. A playing seek resumes playback; a paused seek publishes the decoded target frame and remains paused. The decoder's actual presentation timestamp becomes the current target time used by the existing native-PTS measurement path; the preview frame itself is not passed directly to WASS.

A no-WASS smoke test on the HomeTank_004 right wave video produced:

| Requested | Decoded PTS | Latency |
|---:|---:|---:|
| 20 s | 20.000533 s | 0.201 s |
| 60 s | 60.001600 s | 0.138 s |
| 120 s | 120.003200 s | 0.145 s |

The decoder remained asynchronous. Export-all and selective-export lifecycle paths are covered by smoke tests, including successful shutdown.

## Conclusion

- `SESSION_DELETE_EXIT_BUG_FIXED`
- `VIDEO_RANDOM_SEEK_COMPLETED`
- `WATER_ROI_USER_SELECTION_COMPLETED`
- `SMALL_RESULT_AREA_CAUSED_BY_DEMO_ROI`
- `SPARSE_WASS_SUPPORT_CONFIRMED`
- `CALIBRATION_QUALITY_LIMITATION_CONFIRMED`
- `DEMO_USABILITY_FIX_PASS_WITH_RECONSTRUCTION_WARNING`

The usability defects are fixed. Reconstruction quality remains constrained by the frozen calibration and limited spatial WASS support and requires a separate, evidence-driven task.
