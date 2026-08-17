# Desktop application V0.x architecture

## Product identity

The application is the early form of the future **Stereo Wave Height Measurement System** executable. It is not a phone demo. Recorded stereo videos are the currently available input; professional live cameras will later implement the same input boundary.

## Stable pipeline boundary

```text
InputSource
  |- StereoVideoSource          implemented
  `- LiveStereoCameraSource     abstract placeholder
            |
            v
      StereoFramePair
            |
            v
Calibration -> Synchronization -> WASS -> XYZ -> Grid -> Z0 -> H -> QA -> Visualization/Export
```

`StereoFramePair` carries explicit left/right frame indices, timestamps, payloads, and timestamp provenance. It does not assert that two frames are synchronized merely because their indices match. Downstream code must not branch on device brand or whether the frames came from files or live cameras.

## Implemented V0.x capabilities

- Select left and right recorded video paths in the desktop window.
- Probe width, height, frame count, fps, duration, and timestamp provenance through a replaceable backend.
- Decode explicitly selected frame indices into a standard pair through the optional OpenCV backend.
- Fit the affine clock model $t_R=a t_L+b$ from two or more corresponding flash events.
- Produce tolerance-gated nearest-frame pairs and rejected-frame/residual diagnostics.
- Present final-product tabs for calibration, synchronization, reconstruction, 3-D surface, height map, point wave height, QA, and export as clearly labelled placeholders.

The current environment contains Tkinter but not PySide6, OpenCV, ffprobe, or another reviewed video decoder. Therefore the shell uses Tkinter without adding a large dependency. Selecting files works; metadata/decode becomes available when an approved backend is installed. Absence of a backend raises an explicit error.

Launch from the repository root with the project import path configured:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -m application
```

## Planned progression

| stage | capability |
|---|---|
| V0.1 | stereo video selection, metadata, explicit frame access |
| V0.2 | flash-event time mapping, frame pairing, diagnostics |
| V0.3 | calibration file integration and diagnostics |
| V0.4 | real-video WASS orchestration |
| V0.5 | independent static reference and height field |
| V0.6 | 3-D surface, heat map, point $H(t)$ and QA |
| V0.7 | professional live-camera source |
| V0.8 | hardware acquisition and synchronization |
| V1.0 | professionally calibrated laboratory version |

These labels express development direction; they are not repository releases yet.

## Explicit non-capabilities

- No phone-specific solver, WASS branch, height algorithm, or GUI exists.
- No MER2/Galaxy SDK behavior is invented.
- No automatic unit, timestamp, coordinate, calibration, or camera-setting inference occurs.
- No current GUI action claims to run WASS or produce a height result.
- No phone-stage 1 cm threshold is defined.
