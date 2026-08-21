# HomeTank_004 real-video input inspection

Status: `INPUT_DATA_READY`

This is a read-only input inspection. No checkerboard detector, camera
calibration, WASS stage, stereo reconstruction, or height calculation was run.
The six source MP4 files were not modified.

## Camera roles

Roles come only from `manifest.yaml` and were not inferred from image content:

- cam0 = LEFT = iQOO Neo5S;
- cam1 = RIGHT = iQOO Z10_TurboPlus.

All filenames agree with these roles.

## Video metadata

| Condition | Camera | Size (bytes) | Codec | Resolution | Nominal / average fps | Duration (s) | Frames | Time base | Pixel/color | Rotation |
|---|---|---:|---|---|---|---:|---:|---|---|---:|
| calibration | cam0 LEFT | 320,022,925 | H.264 High | 1920x1080 | 60 / 59.313985 | 117.476511 | 6,968 | 1/90000 | yuv420p, TV, BT.709 | -180 deg |
| calibration | cam1 RIGHT | 107,967,334 | HEVC Main | 1920x1080 | 60 / 59.998472 | 117.336300 | 7,040 | 1/90000 | yuv420p, TV, BT.709 | 0 deg |
| static | cam0 LEFT | 149,193,525 | H.264 High | 1920x1080 | 60 / 59.362109 | 54.664500 | 3,245 | 1/90000 | yuv420p, TV, BT.709 | -180 deg |
| static | cam1 RIGHT | 50,270,700 | HEVC Main | 1920x1080 | 60 / 60.016475 | 54.668300 | 3,281 | 1/90000 | yuv420p, TV, BT.709 | 0 deg |
| wave | cam0 LEFT | 438,552,096 | H.264 High | 1920x1080 | 60 / 59.288709 | 161.177400 | 9,556 | 1/90000 | yuv420p, TV, BT.709 | -180 deg |
| wave | cam1 RIGHT | 148,338,753 | HEVC Main | 1920x1080 | 60 / 59.998436 | 161.170867 | 9,670 | 1/90000 | yuv420p, TV, BT.709 | 0 deg |

All containers identify as the QuickTime/MOV family including MP4. The
different average frame rates and frame counts mean equal frame indices must
not be treated as synchronization evidence.

## Orientation

Raw `-noautorotate` frames confirm the cam0 encoded raster is upside down with
respect to the scene and carries a -180-degree Display Matrix. Canonical cam0
therefore applies exactly one `rotate180`. Cam1 has no rotation metadata and
uses identity. Both canonical streams remain 1920x1080. The MP4 files are not
rewritten; this is a decoding configuration only.

## Representative-frame and common-field inspection

Canonical frames were sampled at 10%, 50%, and 90% of each video and saved
outside the repository under the local diagnostic run directory.

- Calibration: the same physical scene and the complete hand-made black/white
  checkerboard are visible in both cameras at all three sampled times. This is
  presence evidence only, not checkerboard-detection or calibration evidence.
- Static: both cameras show the tank, water region, ruler and common central
  scene at all three sampled times.
- Wave: both cameras show the tank and water region with a common central field
  at all three sampled times.
- Risk: cam0 has a persistent near-lens dark obstruction along the left image
  edge, and the two cameras have noticeably shifted framing. A usable central
  overlap is visible, but its calibrated/rectified extent remains UNKNOWN.

## Synchronization preanalysis

Global mean-luma series were sampled at 10 Hz. After five-sample smoothing,
temporal derivatives were cross-correlated over +/-5 s. The convention is
`offset = t_cam1 - t_cam0`.

| Condition | Candidate offset | Peak correlation | Confidence |
|---|---:|---:|---|
| calibration | 0.0 s | 0.3190 | LOW |
| static | +0.1 s | 0.5352 | MEDIUM |
| wave | 0.0 s | 0.5732 | MEDIUM |

These are candidate starting points only. Global brightness is affected by
different exposure, codec, framing and scene content; it does not establish
frame correspondence. Final synchronization must use the project's timestamp
and event checks before any paired calibration or reconstruction.

## Gate conclusion

All six expected files exist, have non-zero size, expose readable video-stream
metadata, and yield representative decoded frames. Therefore:

`INPUT_DATA_READY`

This gate permits the next task to begin OpenCV calibration preflight. It does
not assert that the checkerboard is detectable, that calibration will pass, or
that the data are ready for WASS.
