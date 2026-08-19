# Real-video feasibility validation

## Position in the project

This is a low-cost real-optics transfer gate inside `stereo-wave-height`, not a new project and not a phone measurement product. Two existing phones provide recorded stereo video before professional-camera purchase:

- cam0 / left: iQOO Z10 Turbo+;
- cam1 / right: iQOO Neo5S.

The purpose is to test whether the established chain remains qualitatively coherent under real lenses, real water, real video encoding, and imperfect file-based synchronization:

```text
left/right video
  -> StereoFramePair
  -> calibration and synchronization
  -> WASS -> XYZ -> coordinate/scale -> gridding
  -> independent Z0 -> H(x,y,t)
  -> QA and visualization
```

The phones are metadata-bearing `Stereo Video File` input sources only. No phone-specific solver, height definition, WASS fork, or final GUI is permitted. The historical ideal-simulation results remain frozen.

## Evidence boundary and gate

This stage does **not** use the professional 1 cm acceptance threshold. It cannot establish phone accuracy, industrial-camera accuracy, or final deployment parameters. It passes when the sign, trend, spatial structure, temporal continuity, and failure diagnostics are physically plausible enough to justify professional-camera procurement.

The formal 1 cm claim remains reserved for professional global-shutter cameras, hardware synchronization, measured calibration, controlled physical references, and a separately frozen laboratory acceptance protocol.

## Required metadata

Every RV experiment must record:

| field | requirement before execution |
|---|---|
| experiment id and date | required |
| cam0/cam1 device identity and role | required |
| resolution, fps, codec | measured from files and cross-checked with device settings |
| focus, exposure, white balance, stabilization | confirmed setting or `UNKNOWN/TODO` |
| physical baseline and working distance | measured, unit m |
| calibration id | required before WASS reconstruction |
| synchronization method and flash events | required |
| WASS config/runtime id | required |
| raw observation support | reported when 3-D output exists |
| status and limitations | `PASS`, `FAIL`, or `BLOCKED`, with evidence |

Raw video, extracted frames, WASS workspaces, xyzC, and large NetCDF products stay outside Git. Git may contain configs, manifests without private paths, small metrics, reports, and deliberately reviewed small screenshots.

## RV0 — Rigid Textured Plane

Purpose: establish real-video calibration, synchronization, image orientation, scale, and WASS input viability before water.

Gate: the reconstructed plane has the correct orientation, no unexplained axis inversion, and no severe scale anomaly. Plane residuals, raw support, and failure stages are reported, but no phone 1 cm claim is made.

## RV1 — Static Water

Purpose: exercise real water optics and construct an independent static reference candidate.

Gate: reconstruction is temporally stable enough to inspect, spatially approximately continuous/planar over an explicitly supported domain, and relative-height trend remains near zero without unexplained sign changes. Reflections and unsupported regions must remain visible in QA.

## RV2 — Static Level Change

Purpose: test non-zero height sign and approximate scale using a measured water addition or independently observed level shift.

Gate: `H=Z-Z0` has the correct sign, shows an overall level increase, and has a broadly reasonable order of magnitude. This is qualitative feasibility, not centimetre-accuracy certification.

## RV3 — Manual Wave

Purpose: test dynamic structure after RV0--RV2 are interpretable.

Gate: crests/troughs, propagation direction, and temporal evolution are physically coherent in supported regions. No large WASS parameter scan or phone-specific correction is allowed.

## Execution order and stop rules

Run RV0 -> RV1 -> RV2 -> RV3. A blocked calibration, synchronization, coordinate/scale, or WASS stage stops the current experiment; do not skip forward or fabricate downstream metrics. Each experiment starts from [the metadata template](experiment_template.md) and the repository configs under `configs/real_video/`.

## Current status

`HomeTank_001` supplied the first uncalibrated static/wave stereo-video pair. Its [input inspection](../../experiments/real_video/HomeTank_001/input_inspection.md) passed conditional input readiness, but the controlled [uncalibrated coarse reconstruction](../../experiments/real_video/HomeTank_001/trial1_reconstruction.md) stopped at WASS autocalibration and is classified `CALIBRATION_REQUIRED`. No stereo xyzC, wave reconstruction, or height result was produced. The next action is a traceable stereo calibration dataset followed by repetition of the static gate; all physical-accuracy claims remain blocked.

`HomeTank_002` is the separately mounted calibrated retry with cam0/left = iQOO Neo5S and cam1/right = iQOO Z10 Turbo+. Its [calibration result](../../experiments/real_video/HomeTank_002/result_summary.md) is `CALIBRATION_DATA_INSUFFICIENT`: the recorded white line grid produced zero complete standard 9 x 6 checkerboard detections, so K/R/T were not fabricated and static/wave WASS were not run. The next action is calibration-target recapture with a rigid alternating black/white board.
