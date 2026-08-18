# HomeTank_001 input inspection

## Scope and evidence

This is an input-feasibility inspection only. It does not run WASS, construct an uncalibrated camera model, calibrate either camera, or produce wave height. The inspection used original MP4 metadata, decoded luminance sequences, and six representative frames stored outside Git under `inspection_frames/`.

Camera identity is fixed by the experiment record:

- `cam0 / left`: iQOO Z10 Turbo+;
- `cam1 / right`: iQOO Neo5S.

The measured vertical height is 1700 mm for each camera. It is not an optical-axis distance. The approximately 2645 mm value is derived from `1700 / sin(40 deg)` and is neither directly measured nor calibration truth.

## File and pair findings

All four expected MP4 files exist and are readable by ffprobe and FFmpeg. Both pairs are 1920 x 1080 with nominal 60 fps, but cam0 is HEVC while cam1 is H.264. Their average rates and frame counts differ, and cam1 has variable/dropped-frame timing evidence. Frame-index-only pairing is therefore invalid; synchronization must use timestamps and common events.

The source files expose no focal-length metadata. No conclusive edit or transcode marker was found in the inspected container metadata, but absence of such a marker does not establish original-camera provenance; this remains `UNKNOWN`.

## Representative-frame review

The following conclusions apply only to the six sampled frames, not every frame:

| Check | Finding |
|---|---|
| Obvious common field of view | `YES`: both cameras contain the tank, water region, rear/side walls, and ruler. |
| Tank visible in both cameras | `YES`. |
| Approximately parallel viewing | `PLAUSIBLE_FROM_SAMPLES`, not geometrically verified. The views differ as expected from baseline, but `R = I` is not established. |
| Ruler visible | `YES` in all sampled views, at different image positions. |
| Water-surface matching texture | `WEAK / RISK`: the surface is largely smooth and low-texture. Visible structure is dominated by reflections, wall deposits, the ruler, and occasional disturbances. |
| Large saturated highlights | No dominant full-frame saturation is evident in the samples; localized bright reflections exist. Quantitative saturation over the full videos is `TODO`. |
| Wave process clear | Surface disturbances are visible in the selected wave frames, but their suitability for dense stereo is not yet established. |
| Automatic crop/zoom change | No obvious change between the selected pre-wave and wave frames. Full-sequence verification is `MANUAL_REVIEW_REQUIRED`. |
| Camera shake | No obvious large rigid shift in the selected samples. Full-sequence verification is `MANUAL_REVIEW_REQUIRED`. |
| Automatic exposure change | Multiple strong common luminance transitions are present. Whether these are deliberate synchronization events, exposure response, or both requires targeted frame review; exposure lock status is `UNKNOWN`. |

The cam0 stream carries `rotation = -180 deg`; cam1 carries no rotation transform. Any future frame adapter must apply or explicitly normalize display orientation before stereo pairing, without silently guessing axis direction.

## Synchronization-event screening

Full-frame mean luminance was sampled at 60 samples/s after a diagnostic 16 x 9 downscale. Multiple strong signed transitions occur at corresponding times in both views and are distinct from ordinary low-amplitude variation. They are recorded as `CANDIDATE_COMMON_EVENTS_FOUND`, not automatically accepted synchronization truth.

For the static pair, six candidate correspondences give the preliminary relation:

`t_right = 0.9981477463 * t_left + 0.074451760 s`

with residual RMSE 0.007829704 s and maximum absolute residual 0.014107640 s.

For the wave pair, eight candidate correspondences give:

`t_right = 0.9998262151 * t_left + 0.071054119 s`

with residual RMSE 0.005361428 s and maximum absolute residual 0.011657261 s.

These fits are suitable only for deciding that common-event synchronization is feasible. Before reconstruction, the event frames and event meaning must be reviewed and a pairing tolerance must be frozen. MP4 `creation_time` differs by seconds between devices and must not be used as the frame offset.

## Readiness decision

Status: `CONDITIONALLY_READY_FOR_UNCALIBRATED_COARSE_K_R_T_DESIGN`.

The inputs are readable, have an obvious common field, contain a visible ruler, and provide candidate common timing events. The next phase may design an explicitly approximate K/R/T initialization, but it must preserve these limitations:

- focal length, principal point, distortion, and true camera rotation remain `UNKNOWN`;
- `R = I` is not verified;
- the 650 mm baseline is a manual measurement, not a calibrated translation vector;
- the water surface has weak natural texture and may not support dense WASS matching;
- timestamp-based pairing and orientation normalization are mandatory;
- no physical height accuracy claim is permitted without calibration and independent validation.
