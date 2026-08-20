# HomeTank_003 calibration evaluation

## Final classification

`CALIBRATION_DATASET_INSUFFICIENT`

`approved_for_wass: false`

All six videos exist and were registered. The calibration gate stopped before
any mono/stereo solve, WASS call, static reconstruction, wave reconstruction,
or height computation.

## Input and target

The experiment-local role assignment is cam0/left = iQOO Neo5S and cam1/right
= iQOO Z10 Turbo+. Canonical display orientation is derived separately for
every file. Calibration and static cam0 require the recorded 180-degree display
transform; wave cam0 has no such transform and also differs in codec/rate.

The configured target is a standard alternating checkerboard with 9 x 6 inner
corners, 10 x 7 physical squares, and `square_size_m=0.020`. The square size is
user-specified/configured and was not independently measured in this task.

## Detection and stop rule

At 0.5 s sampling, cam0 produced 0/270 complete 54-point detections. Cam1
produced 4/270 detections, of which three passed the configured image-quality
gate. A single targeted 10 Hz rescan around 0--3, 68--71, and 125--128 s ruled
out interval aliasing: cam0 remained 0/90, while cam1 produced 13/90 detections
(12 usable).

Consequently there are zero bilateral candidate pairs and zero independent
stereo poses. Position, scale, and orientation diversity are all FAIL. The
minimum threshold of 12 independent pairs is not met, so K/D/R/T were not
estimated and no diagnostic calibration was promoted.

Failure categories are:

- A — checkerboard detection: cam0 complete-grid detection failed;
- B — insufficient bilateral views: no shared valid view exists.

Mono quality, stereo geometry, and rectification were not evaluated rather
than reported as false successes.

## Minimal remedy

Do not rerun WASS on this dataset. First perform a short bilateral target
preflight with the same fixed rig and require 54/54 PASS from both cameras.
Improve only the observable target conditions: use a rigid, flat, high-contrast
printed checkerboard with clean square boundaries, sufficient size, focus, and
lighting. After Gate A passes, record at least 20 independent shared poses and
run Gate B before recording or processing further static/wave data.

The existing static and wave files remain registered and unprocessed. Whether
the rig stayed unchanged after calibration is `UNKNOWN`; this must be resolved
before any future approved calibration is associated with them.
