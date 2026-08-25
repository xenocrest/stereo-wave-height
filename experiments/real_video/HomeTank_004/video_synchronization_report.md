# HomeTank_004 Video Synchronization Analysis

## Method and boundary

The two original wave videos were decoded read-only at 10 Hz and 64 x 36 pixels. Each sample is the whole-frame grayscale mean. Robust derivative outliers identify brightness transitions, and only same-polarity transitions are paired. Camera roles remain `cam0 = LEFT` and `cam1 = RIGHT`.

Light events are used only to estimate video time relation. They do not enter WASS, stereo matching, triangulation, or height calculation; timestamps and source MP4 files are unchanged.

## Video and event result

| Item | Left | Right |
|---|---:|---:|
| Frame count | 9,556 | 9,670 |
| Average FPS | 59.28870921 | 59.99843644 |
| Duration (s) | 161.177400 | 161.170867 |
| 10 Hz brightness samples | 1,612 | 1,612 |
| Candidate transitions | 41 | 20 |

Ten same-polarity transitions agree. With $\Delta t=t_{right}-t_{left}$, the median offset is `0.000 s` and residual RMS is `0.054772 s`. Event-level confidence is `HIGH` under the stated detector rule.

## Interpretation

The correct status is `SYNC_ESTABLISHED_COARSE_BY_LIGHT_EVENTS`, not frame-accurate synchronization. A 10 Hz trace has 0.1 s temporal resolution, while the videos are approximately 60 FPS. Consequently `frame_level_status` remains `SYNC_NOT_ESTABLISHED`; frame-index equality must not be assumed. Future professional deployments should prefer shared trigger/hardware timestamps. For this recording, a higher-rate trace over a manually registered fixed-light ROI is required before full-duration frame pairing.

Machine-readable evidence: [sync_report.yaml](sync_report.yaml).
