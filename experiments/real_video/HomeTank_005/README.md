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
