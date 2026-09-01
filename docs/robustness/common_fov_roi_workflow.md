# Automatic stereo common-FOV and safe water ROI

## Definition and source of truth

The authoritative common field of view is computed from the active calibration package, input image size, and the production rectification policy. OpenCV `stereoRectify` and `initUndistortRectifyMap` produce the two rectified source-valid masks. Their pixelwise intersection is the rectified common-valid mask. This is mapped to the `canonical_cam1` convention used by the GUI and dense-height backend. No image-content matching, hard-coded rectangle, camera-model rule, or per-frame homography is used.

The single implementation is [`src/reconstruction/common_fov.py`](../../src/reconstruction/common_fov.py). Its artifact records calibration identity, image size, rectification alpha/flag, full-canonical bounding box, crop origin, pixel counts, coverage, safety margin, coordinate convention, and a lossless mask. A video size that differs from the calibration size fails with `COMMON_FOV_CALIBRATION_SIZE_MISMATCH`; an empty result fails with `NO_VALID_STEREO_COMMON_FOV`.

## Display and coordinates

The GUI displays only the axis-aligned common-mask bounding box. Invalid islands within that box are grey display-only pixels. If the crop origin is `(x0,y0)`, a displayed crop pixel maps back to the backend coordinate as `u_full = u_crop + x0`, `v_full = v_crop + y0`.

Canvas scale and letterboxing remain handled by the existing display transform. ROI, hover query, result overlay, reference artifact, and export continue to use full `canonical_cam1` coordinates. The backend still extracts original synchronized video frames; a GUI crop is never encoded or sent to WASS.

## Safety and invalidation

The current safety margin is `0 px`: OpenCV source-map validity already supplies the deterministic boundary, and no unvalidated large crop is introduced. The helper supports a recorded 1–2 px erosion if future evidence requires it. ROI validation checks every pixel in the half-open rectangle against the safe mask, not merely four corners. GUI rejection is backed by the same backend validator, which reports `ROI_OUTSIDE_STEREO_COMMON_FOV`.

Changing calibration or either measurement video invalidates the common-FOV artifact, ROI, and reference. Changing ROI continues to invalidate the reference. Legacy exported sessions remain viewable as `LEGACY_COMMON_FOV_UNSPECIFIED`; a new solve requires a current artifact.

## HomeTank_004 geometry smoke

Using the existing calibration and 1920×1080 wave-video mode, without executing WASS, the helper produced:

| Item | Result |
|---|---:|
| Status | `AUTO_STEREO_COMMON_FOV_READY` |
| Full-canonical bbox | `[254, 169, 1190, 815]` |
| Crop origin | `[254, 169]` |
| Safe pixels | 450,901 |
| Frame coverage | 21.7448% |
| Safety margin | 0 px |

Automated tests verify deterministic geometry, asymmetric-FOV reduction, bbox containment, internal-mask rejection, size mismatch, crop/full mapping, and artifact round-trip. Playback performs only an in-memory crop/mask after the one-time calibration/video computation; WASS executions and calibration experiments for this smoke were both zero.
