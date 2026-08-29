# Single-frame Dense Backend Integration

## Result

Classification: `SINGLE_FRAME_DENSE_BACKEND_COMPLETED`.

Freeze status: `BACKEND_FROZEN_FOR_DEMO_INTEGRATION`.

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

## Corrected end-to-end smoke run

The command started from both HomeTank_004 wave videos and requested left time
29.4654055 s. It selected the frozen Case 2 pair (`pts_2651866`, `pts_2646070`)
with 1.0055 ms residual. The established policy-capable binding completed
prepare, match and stereo. The backend produced 35,459 XYZ, H and pixel–XYZ
samples, loaded the polygon, and automatically generated all four dense
artifacts plus the unified result without a second user command.

WASS/reconstruction took 25.1715 s; dense generation took 3.7765 s at the
backend boundary (3.7633 s inside the module). The recorded internal total was
28.9480 s and command wall time was 31.51 s. The remaining approximately
2.5620 s includes frame selection, extraction, lossless staging and report IO;
frame selection was not separately instrumented.

The complete output is retained outside Git at
`D:/stereo-wave-height-runs/HomeTank_004/single-frame-dense-completed-20260829`.

Calibration, synchronization, WASS parameters, reconstruction and MLS policy
were not changed.

Formal demo command:

```powershell
$env:PYTHONPATH='src;.'
python -m src.reconstruction.run_single_frame --config experiments/real_video/HomeTank_004/single_frame_dense_smoke_config.yaml
```

During GUI integration, calibration, synchronization, WASS reconstruction,
height definition, pixel–XYZ, MLS and dense support thresholds are frozen unless
a blocking integration bug is demonstrated.
