# HomeTank_005

- `experiment_id`: `HomeTank_005`
- `raw_data_root`: `D:\research\stereo-wave-height\experiments\real_video\HomeTank_005`
- status: `NOT_PLACED / NOT_PROCESSED`

## Capture design

- new adaptive calibration capture
- LEFT mono full-FOV observations
- RIGHT mono full-FOV observations
- stereo bilateral overlap observations
- wave video contains reference candidate period and wave period
- no dedicated static video
- user-selected reference frame workflow

`cam0 = LEFT` and `cam1 = RIGHT`. The physical camera identities must remain unchanged between calibration and wave capture. Preserve each phone's original video extension; rename only, without transcoding, cropping, frame-rate or resolution changes, re-export, stabilization, or rotation-metadata changes.

## Exact placement checklist

Place the four original files at these paths, replacing `<original_ext>` with each source file's unchanged extension:

```text
D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\calibration\HomeTank_005_calibration_cam0_LEFT.<original_ext>
D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\calibration\HomeTank_005_calibration_cam1_RIGHT.<original_ext>
D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\wave\HomeTank_005_wave_cam0_LEFT.<original_ext>
D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\wave\HomeTank_005_wave_cam1_RIGHT.<original_ext>
```

There is intentionally no `static/` directory. The user will seek within the wave pair, choose a reference frame, run the reference solve, and establish the reference plane through the existing workflow.

## Static compatibility check

The existing GUI file selectors and calibration/capture interfaces accept arbitrary supported local video paths and preserve original files. The current packaged-resource defaults and Windows build script still name `HomeTank_004`; these are demo defaults, not a restriction on selecting HomeTank_005 videos. No source code is changed in this preparation task.
## Intake QA result

- Four source videos: present, readable, 1920×1080, approximately 30 fps, and SHA-256 bound; see `intake_qa/input_manifest.yaml`.
- Canonical imaging mode and PTS: compatible / `SYNC_INPUT_READY`.
- Split capture QA: LEFT `LEFT_MONO_INSUFFICIENT` (3/9), RIGHT `RIGHT_MONO_READY` (4/9), stereo `STEREO_OVERLAP_READY` (5/9).
- Final intake classification: `HOMETANK005_CAPTURE_INSUFFICIENT`. Formal calibration was not run.

| Role | Actual file | SHA-256 |
|---|---|---|
| calibration cam0 / LEFT | `HomeTank_005_calibration_cam0_LEFT.mp4` | `793cd46adc997447b0f7c2eb27194325edaa194d49ba49ff57cd71867a779210` |
| calibration cam1 / RIGHT | `HomeTank_005_calibration_cam1_RIGHT.mp4` | `651455f9e182cc3c57d5ba06540da5b2b8885c41cf1276a148cd395f34c60fb4` |
| wave cam0 / LEFT | `HomeTank_005_wave_cam0_LEFT.mp4` | `58ec63807007ced7d4f6b46da8c53d6d4b9187d8133f4060eefb915d4e29eb930` |
| wave cam1 / RIGHT | `HomeTank_005_wave_cam1_RIGHT.mp4` | `ee25826b6c1a71235765c903d73269bfb865c459379c02c8d40a5343f4061f50` |
