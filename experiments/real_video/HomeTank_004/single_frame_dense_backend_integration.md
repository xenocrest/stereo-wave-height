# Single-frame Dense Backend Integration

## Result

Classification: `SINGLE_FRAME_DENSE_BACKEND_PARTIAL`.

The optional dense-height stage is now connected directly after a successful
single-frame reconstruction. A request can carry a canonical-cam1 polygon ROI;
when enabled, the backend passes its generated pixel–XYZ, height samples,
projection matrix, calibrated baseline and frozen reference plane directly to
the unchanged MLS dense-map module. `enabled: false` preserves the prior result
status and does not invoke dense processing.

## Frozen Case 2 polygon validation

The conservative demo polygon was selected from visible water in the canonical
cam1 image only:

```text
[(700,340), (900,340), (900,520), (700,520)]
```

It contains 36,381 pixels: 1,950 OBSERVED (5.3599%), 8 ESTIMATED
(0.0220%), and 34,423 UNSUPPORTED (94.6181%). There are 1,958 valid heights;
minimum/maximum/mean/median are -25.4970/-16.7430/-24.3001/-24.6615 mm.
Generation took 3.7182 s. The manual Case 2 pixel `(799,396)` lies inside this
polygon but remains `UNSUPPORTED`; no support rule was relaxed.

## One permitted end-to-end smoke run

The command started from both HomeTank_004 wave videos and requested left time
29.4654055 s. It selected the frozen Case 2 pair (`pts_2651866`, `pts_2646070`)
with 1.0055 ms residual. The run stopped after 14.1757 s while parsing the
stereo configuration: the smoke configuration initially selected the official
runtime, whose stereo executable does not accept the frozen policy-capable key
`RECTIFICATION_ALPHA`.

This is a runtime-binding selection error, not a dense-map numerical failure.
The config now points to the already established policy-capable binding, but no
second WASS run was made because this task explicitly allowed only one new run.
Consequently, the code integration and frozen polygon result pass, while the
new video-to-dense smoke closure remains unproven in this turn. The external
failed-run evidence is retained at
`D:/stereo-wave-height-runs/HomeTank_004/single-frame-dense-smoke-20260829`.

Calibration, synchronization, WASS parameters, reconstruction and MLS policy
were not changed.
