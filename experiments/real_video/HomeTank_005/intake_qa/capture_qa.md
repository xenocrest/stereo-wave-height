# HomeTank_005 split-capture QA

Status: `HOMETANK005_CAPTURE_INSUFFICIENT`

This is checkerboard detection and capture observability QA only. `calibrateCamera`, `stereoCalibrate`, and WASS executions are zero.

| Branch | Sampled | Detected/candidates | Grid | Occupied | Classification |
|---|---:|---:|---|---:|---|
| LEFT mono | 717 | 179 | `[0, 0, 0, 38, 140, 0, 1, 0, 0]` | 3/9 | `LEFT_MONO_INSUFFICIENT` |
| RIGHT mono | 717 | 86 | `[0, 2, 0, 14, 69, 1, 0, 0, 0]` | 4/9 | `RIGHT_MONO_READY` |
| Stereo overlap | — | 63 | `[0, 0, 1, 0, 0, 1, 12, 7, 42]` | 5/9 | `STEREO_OVERLAP_READY` |

The split model was applied correctly: mono candidates are independent, while stereo uses only bilateral same-time detections and overlap-normalized occupancy. Bilateral full-image 9/9 coverage was not required.

## Diversity and image quality

- LEFT scale area ratio: 1.780; perspective min/median/max: `[0.016854052700920056, 0.024925681051772994, 0.12017882420195886]`.
- RIGHT scale area ratio: 1.841; perspective min/median/max: `[0.05169900436350197, 0.0720854083669358, 0.16895471661980932]`.
- LEFT sharpness P10/median/P90: `[224.02784354372568, 743.4009191736533, 903.9242909759495]`.
- RIGHT sharpness P10/median/P90: `[666.7712722369912, 1254.4438677766777, 1399.4242057504305]`.
- Bilateral near-duplicate ratio: 0.762; diverse estimate: 15.
- Checkerboard ROI clipping is not severe: LEFT dark/bright median 0.000000/0.000000; RIGHT 0.001610/0.000000.

## Historical comparison

| Metric | HomeTank_004 | HomeTank_005 |
|---|---:|---:|
| LEFT mono occupied cells | 3/9 | 3/9 |
| RIGHT mono occupied cells | 3/9 | 4/9 |
| Stereo overlap occupied cells | 6/9 | 5/9 |
| Bilateral candidates | 192 | 63 |

RIGHT mono coverage improved by one cell. LEFT mono coverage did not expand beyond 3/9, and its top/right full-FOV observations remain absent. Stereo overlap is usable (5/9) but slightly less occupied than the historical 6/9. Candidate count alone is not used as the decision criterion.

## Gate

`CALIBRATION_OBSERVABILITY_PRECHECK = INSUFFICIENT`. Formal split calibration is not started because LEFT intrinsic observability remains spatially concentrated. This report does not initiate salvage or recommend another recording; it records the missing information for the next decision.
