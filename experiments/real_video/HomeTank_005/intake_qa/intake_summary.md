# HomeTank_005 intake summary

Final classification: `HOMETANK005_CAPTURE_INSUFFICIENT`

## Input and timing

All four uniquely named source MP4 files are non-zero, readable, hashed, and retained unchanged. Calibration and wave use compatible 1920×1080 canonical modes: LEFT carries 180° display rotation and maps to `rotate180`; RIGHT is identity. Both pairs have monotonic, duplicate-free, CFR-like PTS and are `SYNC_INPUT_READY`. Camera identity is `CAMERA_IDENTITY_ASSUMED_FROM_CAPTURE_MANIFEST`; no conflicting metadata was found.

## Capture QA

- LEFT mono: 179 candidates, 3/9 cells, `LEFT_MONO_INSUFFICIENT`.
- RIGHT mono: 86 candidates, 4/9 cells, `RIGHT_MONO_READY`.
- Stereo: 63 bilateral pairs, 5/9 overlap-normalized cells, `STEREO_OVERLAP_READY`.
- Observability precheck: `INSUFFICIENT`, specifically because LEFT mono full-FOV support remains concentrated.

## Wave scene

Representative times: `[12.07367, 48.29468, 90.552525]` s. Bright clipping and glare proxies are negligible. LEFT/RIGHT brightness differences are about 11.39–17.96 gray levels. The later RIGHT samples show local low-texture ratios near 0.640; this is a later scene-aware matching/confidence concern, not an intake corruption. Motion proxy confirms `WAVE_DYNAMIC_RANGE_PRESENT`. A relatively low-motion reference candidate was found at 7.5–10.5 s; this is a candidate, not proof of absolute still water.

Formal geometric common FOV remains `COMMON_FOV_PENDING_NEW_CALIBRATION`; HomeTank_004 calibration was not applied.

Warnings: `['LEFT_MONO_SPATIAL_COVERAGE_INSUFFICIENT', 'BILATERAL_POSE_DUPLICATION_HIGH', 'RIGHT_WAVE_LOCAL_LOW_TEXTURE_RISK']`. No re-recording recommendation is issued. Formal split calibration is **not permitted by the current precheck**; no automatic salvage search is started.
