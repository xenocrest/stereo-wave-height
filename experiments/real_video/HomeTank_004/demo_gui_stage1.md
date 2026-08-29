# HomeTank_004 Offline Demo GUI — Stage 1

## Classification

`DEMO_GUI_STAGE1_COMPLETED`

## Technology and boundary

The runnable desktop shell uses the repository's existing Tkinter/Pillow desktop stack. No new GUI dependency was introduced. The application is fully offline and calls the frozen single-frame backend through a subprocess:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -m application
```

The GUI only creates a request configuration, invokes `python -m src.reconstruction.run_single_frame`, and reads the unified result. It does not change calibration, synchronization, WASS, height, pixel–XYZ, MLS, direct-observation, or hole-support algorithms.

## Supported Stage 1 functions

- Editable LEFT/RIGHT camera fields and loading of existing calibration YAML.
- Persistent display of K/D, stereo R/T, baseline in metres, calibration status, stereo RMS, and epipolar RMS.
- LEFT/RIGHT calibration-video selection and first-frame preview; recalibration remains disabled for Stage 2.
- LEFT/RIGHT measurement-video selection and offline FFmpeg metadata inspection.
- Main RIGHT/canonical-cam1 preview, Play, Pause, timeline, and current-time selection.
- Non-blocking worker-thread invocation of the frozen backend; duplicate requests are rejected while running.
- Automatic loading of selected frame, dense height PNG, dense status PNG, and unified summary.
- Persistent `MeasurementRecord` history with same-time naming `29.465s`, `29.465s_02`, etc.
- External session storage and `session.log` under `D:\stereo-wave-height-runs\gui_sessions\<session_id>`; sessions are retained on exit.
- User-readable failures for missing input, calibration, backend results, and required artifacts.

## Smoke evidence

The existing completed result at `D:\stereo-wave-height-runs\HomeTank_004\single-frame-dense-completed-20260829` was first loaded through the GUI result parser. One final Stage-1 backend smoke used the same GUI runner path, HomeTank_004 Wave, and target `29.4654055 s`. Its classification and exact session directory are recorded after execution below.

- GUI-triggered WASS executions in this task: **1**
- Target time: **29.4654055 s**
- Backend classification: `SINGLE_FRAME_DENSE_HEIGHT_COMPLETED`
- GUI runner smoke directory: `D:\stereo-wave-height-runs\gui_sessions\stage1-smoke-20260829-fixed\measurement_29.465s`
- XYZ points: **35,459**
- Backend-reported total time: **28.5093 s**
- Result display artifacts: selected RIGHT frame, dense height PNG, dense status PNG

This remains a diagnostic HomeTank_004 demonstration. It does not change the preserved calibration-quality warning or claim engineering measurement accuracy.

## Deferred to Stage 2

- Original/height alpha overlay.
- Mouse hover query for pixel, XYZ, H, and status.
- Interactive point-cloud viewer.
- Selective export and exit-time export/delete dialog.
- Calibration execution wiring and ROI drawing.
