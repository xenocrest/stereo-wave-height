# Packaged Demo Repeated Backend Failure Diagnosis

## Scope

This diagnosis addresses the three random measurements in GUI session
`20260830-170032`. It does not change calibration mathematics, synchronization,
WASS parameters, height computation, MLS, ROI, or dense-support policy.

## Evidence

The requested times were `28.834100 s`, `31.634178 s`, and `38.717700 s`.
Every target and every bounded neighbor produced the same structured backend
warning before WASS execution:

```text
Fixed-calibration reconstruction terminated: ValueError: WASS fixed calibration differs from OpenCV source: intrinsics_00.xml
```

The GUI-generated calibration file contained the newly computed OpenCV K/D/R/T,
while each request pointed `wass_config_dir` at the distribution's frozen
HomeTank_004 XML set. The numerical-consistency guard correctly rejected this
mixed calibration. The subprocess wrapper then reduced the structured failure
to exit code 1, and the fallback policy incorrectly treated every exception as
frame-local.

## Fix

- Each measurement candidate receives a unique copied WASS configuration
  directory. Matcher/stereo policy files remain unchanged.
- The six fixed-calibration XML matrices are regenerated from the calibration
  YAML selected in the GUI and are checked by the existing strict verifier.
- Nonzero backend exits first parse `single_frame_result.json`; the stage,
  original warning, and log path survive the subprocess boundary.
- Neighbor fallback is eligible only for explicitly classified frame-local
  reconstruction-support failures. Configuration/runtime/calibration/I/O and
  serialization failures stop immediately.
- The existing bounded order remains `0, -1, +1, -2, +2` and continues to shift
  the synchronized pair target through the established R0 mapping.
- A dense result with no valid ROI support now writes an all-`UNSUPPORTED`
  artifact instead of indexing an empty array. This is an engineering boundary
  fix and does not infer any height.

## Real packaged-path verification

The first user-failed target, `28.834100 s`, was executed once through the
rebuilt packaged `StereoWaveHeightDemo.exe --backend-single-frame` path.

- Fallback offset: `0`
- WASS reconstruction: completed
- XYZ points: `2,877`
- Pixel-XYZ correspondences: `2,877`
- Point-height H output: generated
- Dense ROI: `36,381` pixels, all `UNSUPPORTED` for this calibration/frame
- Dense diagnostic artifacts: generated without fabricated values

The target therefore disproves the earlier frame-support interpretation of the
repeated exit-code failures. Core reconstruction is available, while the fixed
demo ROI has no valid dense support under this newly generated calibration.
That limitation remains explicit and is not converted into a successful height
claim.

## Classification

- Root cause: `PACKAGED_SELECTED_CALIBRATION_WASS_XML_MISMATCH`
- Engineering fix: `REPEATED_RANDOM_FRAME_ENGINEERING_FAILURE_FIXED`
- Demo result: `DEMO_RANDOM_FRAME_RELIABILITY_PARTIAL`

