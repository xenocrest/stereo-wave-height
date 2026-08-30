# HomeTank_004 Demo Readiness Checklist

Readiness result: `DEMO_READINESS_PASS` (validated 2026-08-30). The complete launch-to-export flow passed with one GUI-triggered `29.4654055 s` reconstruction; backend-reported total time was `30.5388 s`. No demo blocker was found.

## Before demo

- Environment: Windows, repository Python environment, local WASS runtime and FFmpeg available.
- Launch: `$env:PYTHONPATH="$PWD;$PWD\src"; python -m application`
- Calibration: `experiments/real_video/HomeTank_004/calibration_result.yaml`
- Videos: HomeTank_004 calibration and wave LEFT/RIGHT MP4 files under `videos/`.
- Expected single-frame backend time: approximately 30 seconds.
- Keep `D:\stereo-wave-height-runs\gui_sessions` writable and allow the result window to remain responsive while processing.

## Demo flow

1. Launch and load the existing calibration.
2. Select calibration videos and preview both sides.
3. Select LEFT/RIGHT measurement videos.
4. Play, seek, and pause near `29.4654055 s`.
5. Select **解算当前帧** and wait for completion.
6. Show original, overlay, height, and status modes; hover OBSERVED/ESTIMATED/UNSUPPORTED pixels.
7. Open and close the original WASS point-cloud viewer.
8. Continue playback, then reopen the historical measurement.
9. Exit through export all, selective export, delete all, or cancel.

## Known limitations

- The Case 2 ROI is approximately 5.36% OBSERVED, 0.022% ESTIMATED, and 94.62% UNSUPPORTED; unsupported pixels remain N/A.
- ESTIMATED XYZ is not persisted and is shown as N/A.
- The application is not packaged as an EXE.
- WASS processing is approximately 30 seconds per selected frame and is not real-time.
